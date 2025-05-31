# idTech 2 BSP Blender Importer
This addon is to import .BSP files directly into Blender.
Tested with Anachronox, but format should be the same as Quake II.

Note that lightmaps have not been incorporated.  I'm not sure how that would best translate,
I'll add it if I see a sensible way to have it affect a material setting or something, but otherwise,
of course, that sort of thing can be done in Blender.

Currently, addon will simply search all the files with appropriate extensions within the working directory,
so make sure all textures that the .BSP file needs/refers to are somewhere within the folder the .BSP file 
was opened from.

This addon does not (yet, at least) attempt to import models and/or entities referred to by the .BSP file.

![image](https://github.com/user-attachments/assets/cc4cce35-0cda-4902-8784-7d7410ecdd0e)


### .WAL images
Support has been added for .wal images, commonly used in Quake II.
These, along with other files, need to be extracted from the Quake II PAK files.
This tool will make that easy: https://github.com/GeneralProtectionFault/PAKExtract

When these PAK files are extracted, the result is typically the .BSP files in one folder, and instead of the textures being in child folders,
the textures folder is at the same level as the one w/ the .BSPs.  Because of this,and how the addon searches for all acceptable image files,
an option has been added to search all files within the *parent* of the folder containing the loaded .BSP file:
![image](https://github.com/user-attachments/assets/58c1dd41-a194-403b-8e96-45c304041be5)

Also, because Blender will not recognize a .WAL file, the addon will parse .WAL files and write a .PNG file in the same folder.
Be aware of this if you want to keep the folder clean, etc... or a copy can be made.  

## BSP Structure Diagram
Please note this is almost certainly not perfect, and is almost certainly missing some information regarding brushes/leaves/etc... which are not necessary for 
simply importing the map, but I used this when making this plugin, and I think can provide useful, digestable information, which is not easy
to find all in 1 spot these days:
![Diagram](Anachronox_BSP_Structure.drawio.svg)
