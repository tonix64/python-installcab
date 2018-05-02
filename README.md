# python-installcab

Extract and install components from cab based installers

## Experimental

The software is  **experimental** so you should try it in a fresh wineprefix or make a backup of your wineprefix just in case (at least windows folder and .reg files at the root of your wineprefix).

## Usage:

```
python cabinstall.py cabfile component [wineprefix_path]
```

- cabfile: an exe installer that can be extracted with cabextract
- component: a prefix for one of the components inside the cab file
- wineprefix_path: you can set this, otherwise it will try to get from your WINEPREFIX environment variable
- wine: wine binary name, in case you need to run this with wine64 (only used for importing registry entries)

## Example

```
python cabinstall.py ~/.cache/winetricks/win7sp1/windows6.1-KB976932-X86.exe x86_microsoft-windows-mediafoundation"
```

You can also try the [install-mf.sh](install-mf.sh) file that installs WMF components from win7sp1 installer. There is also [install-mf-64.sh](install-mf-64.sh) for installing into a 64 bit wineprefix.

Note you will need to run `winetricks mf` first so the installer will be cached (for now install-mf.sh does not download the installer, but relies on winetricks to have done it beforehand).

## What exactly it does

1. Extracts from the cab file using cabextract with 'component' as filter
2. Finds out what dll files and manifest files where extracted
3. Will place dll files in $WINEPREFIX/windows/system32/ or syswow64 depending on arch
4. Will convert manifest data to .reg file and import it through wine/wine64

The software doesn't try to find out dependencies or be smart about where to install dlls, it will just install dlls in the system32 or syswow64 directory, and import stuff into wine's registry from manifest files.

It does not aim to fully support cabinet installers, but is capable of installing just parts from an installer, going a bit further than what is actually possible with 'proper' support.

## Dependencies

- python
- cabextract

## License

This software is released into the Public Domain by use of the Unlicense, see the [LICENSE](LICENSE) file
for more details.

