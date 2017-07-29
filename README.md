# YCM-AOSP-Generator
A fork from YCM-Generator reworked to support only AOSP project/subprojects and its peculiarities.


_**Still a work in progress**_

This is a script which generates a list of compiler flags from a project with an AOSP subproject. It can be used to:

* generate a ```.ycm_extra_conf.py``` file for use with [YouCompleteMe](https://github.com/Valloric/YouCompleteMe)
* generate a ```.color_coded``` file for use with [color_coded](https://github.com/jeaye/color_coded)


_TODO improve readme_

## Usage
Run ```./config_gen.py -m MODULE AOSP_DIR```, where ```AOSP_DIR``` is the root AOSP directory and ```MODULE``` is the relative path
for the AOSP module you want to generate conf files for.

## Requirements and Limitations
* Requirements:
    + Python 2
    + Clang

* Supported build systems:
    + AOSP build system

## Documentation & Support
* run ```./config_gen.py --help``` to see the complete list of supported options.

## Development
Patches are welcome. Please submit pull requests against the ```develop``` branch.

## License
YCM-AOSP-Generator is published under the GNU GPLv3.

