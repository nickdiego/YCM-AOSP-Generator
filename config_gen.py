#!/usr/bin/env python2

import sys
import os
import os.path
import re
import argparse
import datetime
import multiprocessing
import shlex
import shutil
import tempfile
import time
import subprocess
import glob
import json


# Default flags for make
default_make_flags = ["-i", "-j" + str(multiprocessing.cpu_count())]

# Set YCM-Generator directory
# Always obtain the real path to the directory where 'config_gen.py' lives as,
# in some cases, it will be a symlink placed in '/usr/bin' (as is the case
# with the Arch Linux AUR package) and it won't
# be able to find the plugin directory.
ycm_generator_dir = os.path.dirname(os.path.realpath(__file__))


def main():
    # parse command-line args
    parser = argparse.ArgumentParser(description="Automatically generates config files for YouCompleteMe")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show output from build process")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite the file if it exists.")
    parser.add_argument("-F", "--format", choices=["ycm", "cc", "clang", "cdb", "all"], default="ycm", help="Format of output file (YouCompleteMe or color_coded). Default: ycm")
    parser.add_argument("-M", "--make-flags", help="Flags to pass to make when fake-building. Default: -M=\"{}\"".format(" ".join(default_make_flags)))
    parser.add_argument("-o", "--output", help="Save the config file as OUTPUT. Default: .ycm_extra_conf.py, or .color_coded if --format=cc.")
    parser.add_argument("-m", "--module", default="bionic/libc", help="Choose specific module to build/generate flags for. Default: all")
    parser.add_argument("-p", "--include-prefix", help="Prefix path to be concatenated to each include path flag. Default: aosp_dir")
    parser.add_argument("AOSP_DIR", help="The root directory of the project.")
    args = vars(parser.parse_args())
    aosp_dir = os.path.abspath(args["AOSP_DIR"])

    # verify that aosp_dir exists
    if(not os.path.exists(aosp_dir)):
        print("ERROR: '{}' does not exist".format(aosp_dir))
        return 1

    # sanity check - remove this after we add Windows support
    if(sys.platform.startswith("win32")):
        print("ERROR: Windows is not supported")

    force = args["force"]
    include_path_prefix = aosp_dir if args["include_prefix"] is None else args["include_prefix"]
    outformat = args.pop("format")
    formats = [ "ycm", "cc", "clang", "cbd" ] if outformat == "all" else [ outformat ]

    # command-line args to pass to fake_build() using kwargs
    args["make_flags"] = default_make_flags if args["make_flags"] is None else shlex.split(args["make_flags"])
    del args["force"]
    del args["output"]
    del args["include_prefix"]
    del args["AOSP_DIR"]

    tmp_dir=os.path.join(ycm_generator_dir, "logs")
    with open("build-full.log", "r") as build_log:
    # with tempfile.NamedTemporaryFile(mode="rw", dir=tmp_dir, delete=False) as build_log:
        print("## Processing build commands..")
        (count, skipped, compile_db) = parse_flags(build_log, include_path_prefix)
        config_file = os.path.join(aosp_dir, args["module"], "compile_commands.json")
        print("## Writing compilation database with {} entries to {}".format(len(compile_db), config_file))
        generate_compile_db_file(compile_db, config_file)
        print("## Done.")


def fake_build(aosp_dir, build_log, verbose, make_flags, module):
    '''Builds the project using the fake toolchain, to collect the compiler flags.

    aosp_dir: the directory containing the source files
    build_log_path: the file to log commands to
    verbose: show the build process output
    make_flags: additional flags for make
    '''
    assert(not sys.platform.startswith("win32"))

    # environment variables and arguments for build process
    started = time.time()
    FNULL = open(os.devnull, "w")
    proc_opts = {
        "stdin": FNULL,
        "stderr": FNULL,
        "stdout": build_log
    }
    proc_opts["cwd"] = aosp_dir
    env = os.environ

    # helper function to display exact commands used
    def run(cmd, *args, **kwargs):
        # print("$ " + " ".join(cmd))
        subprocess.call(cmd, *args, **kwargs)

    # Just a sanity check
    if os.path.exists(os.path.join(aosp_dir, "build/envsetup.sh")):
        module_flag = "BUILD_MODULES_IN_PATHS={}".format(module)
        make_args = [ "make" ] + make_flags + [ "-Bnk", "-C", aosp_dir, "-f",
                "build/core/main.mk", "all_modules", module_flag ]
        print("## Getting compile flags (this may take some time)...")
        run(make_args, env=env, **proc_opts)
    else:
        print("ERROR: Unknown build system")
        sys.exit(2)
    print("## Build completed in {} sec".format(round(time.time() - started, 2)))


def parse_flags(build_log, include_path_prefix):
    '''Creates a list of compiler flags from the build log.

    build_log: an iterator of lines
    Returns: (line_count, skip_count, flags)
    flags is a list, and the counts are integers
    '''

    # make sure we will process file from its beggining
    build_log.seek(0)

    # Used to ignore entries which result in temporary files, or don't fully
    # compile the file
    ignore_regex = re.compile("(-x assembler)|(-o ([a-zA-Z0-9._].tmp))|(/dev/null)")
    skip_count = 0

    cc_compile_regex = re.compile("(^.*-?gcc )|(^.*-?clang )")
    cpp_compile_regex = re.compile("(^.*-?g\+\+ )|(^.*-?clang\+\+ )")

    # Flags we want:
    # -includes (-i, -I)
    # -warnings (-Werror), but no assembler, etc. flags (-Wa,-option)
    # -language (-std=gnu99) and standard library (-nostdlib)
    flags_whitelist = ["-[iIDF].*", "-W[^,]*", "-(no)?std(lib|inc)"]
    flags_whitelist = re.compile("|".join(map("^{}$".format, flags_whitelist)))

    # macro definitions should be handled separately, so we can resolve duplicates
    # -defines (-D)
    define_flags = dict()
    define_regex = re.compile("-D([a-zA-Z0-9_]+)=(.*)")

    # let's handle arch flag separately also
    # -word size (-m64)
    arch_regex = re.compile("-m[0-9]+")

    # Used to only bundle filenames with applicable arguments
    filename_flags = ["-o", "-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]
    invalid_include_regex = re.compile("(^.*out/.+_intermediates.*$)|(.+/proguard.flags$)")

    file_regex = re.compile("(^.+\.c$)|(^.+\.cc$)|(^.+\.cpp$)|(^.+\.cxx$)")

    compile_db = []
    line_count = 0
    compiler = None

    # Process build log
    for line in build_log:

        if (cc_compile_regex.match(line)):
            compiler = 'cc'
        elif (cpp_compile_regex.match(line)):
            compiler = 'cpp'
        else:
            continue

        if (ignore_regex.search(line)):
            skip_count += 1
            continue

        arguments = [ compiler ]
        line_count += 1
        words = split_flags(line)
        filepath = None

        for (i, word) in enumerate(words):
            if (file_regex.match(word)):
                filepath = word

            if(word[0] != '-' or not flags_whitelist.match(word)):
                continue

            # handle macro definitions
            m = define_regex.match(word)
            if(m):
                if(m.group(1) not in define_flags):
                    define_flags[m.group(1)] = [m.group(2)]
                elif(m.group(2) not in define_flags[m.group(1)]):
                    define_flags[m.group(1)].append(m.group(2))
                continue

            # include arguments for this option, if there are any, as a tuple
            if(i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-'):
                p = os.path.join(include_path_prefix, words[i+1])
                if not invalid_include_regex.match(p):
                    arguments.extend([word, p])
            else:
                if word.startswith("-I"):
                    opt = word[0:2]
                    p = os.path.join(include_path_prefix, word[2:])
                    if not invalid_include_regex.match(p):
                        arguments.append(opt + p)
                else:
                    arguments.append(word)

        if (filepath == None):
            # print("Empty file name. Ignoring: {}".format(line))
            skip_count += 1
            continue

        # add entry to database
        # print("adding entry args={}".format(len(arguments)))
        compile_db.append({
            'directory': include_path_prefix,
            'file': filepath,
            'arguments': arguments
            })

    return (line_count, skip_count, compile_db)


def generate_compile_db_file(compile_db, config_file):
    '''Generates compile db file

    compile_db: compile db set
    config_file: the path to save the configuration file at'''

    with open(config_file, "w") as output:
        json.dump(compile_db, output, indent=True)


def generate_ycm_conf(flags, config_file):
    '''Generates the .ycm_extra_conf.py.

    flags: the list of flags
    config_file: the path to save the configuration file at'''

    template_file = os.path.join(ycm_generator_dir, "template.py")

    with open(template_file, "r") as template:
        with open(config_file, "w") as output:
            output.write("# Generated by YCM Generator at {}\n\n".format(str(datetime.datetime.today())))

            for line in template:
                if(line == "    # INSERT FLAGS HERE\n"):
                    # insert generated code
                    for flag in flags:
                        if(isinstance(flag, basestring)):
                            output.write("    '{}',\n".format(flag))
                        else: # is tuple
                            output.write("    '{}', '{}',\n".format(*flag))

                else:
                    # copy template
                    output.write(line)


def split_flags(line):
    '''Helper method that splits a string into flags.
    Flags are space-seperated, except for spaces enclosed in quotes.
    Returns a list of flags'''

    # Pass 1: split line using whitespace
    words = line.strip().split()

    # Pass 2: merge words so that the no. of quotes is balanced
    res = []

    for w in words:
        if(len(res) > 0 and unbalanced_quotes(res[-1])):
            res[-1] += " " + w
        else:
            res.append(w)

    return res


def unbalanced_quotes(s):
    '''Helper method that returns True if the no. of single or double quotes in s is odd.'''

    single = 0
    double = 0

    for c in s:
        if(c == "'"):
            single += 1
        elif(c == '"'):
            double += 1

    return (single % 2 == 1 or double % 2 == 1)


if(__name__ == "__main__"):
    # Note that sys.exit() lets us use None and 0 interchangably
    sys.exit(main())

