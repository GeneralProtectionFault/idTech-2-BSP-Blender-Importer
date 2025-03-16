This addon is to import .BSP files directly into Blender.
Tested with Anachronox, but format should be the same as Quake II.
However, .WAL image support is not yet implemented, but planned so long as I can Python-ify that.

Currently, addon will simply search all the files with appropriate extensions within the working directory,
so make sure all textures that the .BSP file needs/refers to are somewhere within the folder the .BSP file 
was opened from.

This addon does not (yet, at least) attempt to import models and/or entities referred to by the .BSP file.

![image](https://github.com/user-attachments/assets/cc4cce35-0cda-4902-8784-7d7410ecdd0e)


.WAL images
Support has been added for .wal images, commonly used in Quake II.
These, along with other files, need to be extracted from the Quake II PAK files.
This tool will make that easy: https://github.com/GeneralProtectionFault/PAKExtract

When these PAK files are extracted, the result is typically the .BSP files in one folder, and instead of the textures being in child folders,
the textures folder is at the same level as the one w/ the .BSPs.  Because of this,and how the addon searches for all acceptable image files,
an option has been added to search all files within the *parent* of the folder containing the loaded .BSP file:
![image](https://github.com/user-attachments/assets/58c1dd41-a194-403b-8e96-45c304041be5)

Also, because Blender will not recognize a .WAL file, the addon will parse .WAL files and write a .PNG file in the same folder.
Be aware of this if you want to keep the folder clean, etc... or a copy can be made.  
