# idTech 2 BSP Blender Importer
This addon is to import .BSP files directly into Blender.
Tested with Anachronox, but format should be the same as Quake II.

A first attempt at incorporating lightmaps (optional - check box on import to activate).
I suspect it isn't quite right because while some maps look decent, others are too black, etc...
It's also not always desirable to use them if you're going to do lighting elsewhere.  However,
there is a lightmap influence option to adjust the "weight" of them.  In some cases, this makes sense,
such as the effect being significant enough to affect the color--but applying them fully would
be too much.

Currently, addon will simply search all the files with appropriate extensions within the working directory,
so make sure all textures that the .BSP file needs/refers to are somewhere within the folder the .BSP file 
was opened from.

This addon does not (yet, at least) attempt to import models and/or entities referred to by the .BSP file.
There is currently an option to add en empty for each entity that has an orign/location to put it at, to at least show the information.

![image](https://github.com/user-attachments/assets/cc4cce35-0cda-4902-8784-7d7410ecdd0e)
<img width="2049" height="873" alt="image" src="https://github.com/user-attachments/assets/6dc978a6-7e9d-46e9-8c4e-aede1a8319e7" />


### .WAL images
Support has been added for .wal images, commonly used in Quake II.
These, along with other files, need to be extracted from the Quake II PAK files.
This tool will make that easy: https://github.com/GeneralProtectionFault/PAKExtract

When these PAK files are extracted, the result is typically the .BSP files in one folder, and instead of the textures being in child folders,
the textures folder is at the same level as the folder w/ the .BSPs.  Because of this,and how the addon searches for all acceptable image files,
an option has been added to search all files within the *parent* of the folder containing the loaded .BSP file:
<img width="1105" height="703" alt="image" src="https://github.com/user-attachments/assets/152803cd-a008-425c-a083-895b44e14194" />

BE CAREFUL WITH THIS OPTION.  It's designed to facilitate finding texture images in the original folder structure, but if you search a "parent" folder
that goes outside your game directory, you'll potentially hang Blender for a while as it tries to find all the textures in however large/nested a folder it was pointed to.

For games like Anachronox, in which the textures are typically within the same folder, leave this at 0.
For Quake II (extracting from the .PAK while preserving the folder structure), this would typically be set to 1 or 2, depending on the .BSP being imported.
There is a "maps" folder in the main directory, and other levels have specific folders, like chaos/maps, for example.
If extracting the .PAK files, there's a "textures" folder.  Assuming that's in the main directory, both situations refer to this textures folder.
Ergo, in the first example, set the Parent Levels to 1, in the second example, set it to 2.
Naturally, if you set the folders up yourself, this doesn't apply.  This is a somewhat icky attempt to handle the "natural" folder structure.


Also, because Blender will not recognize a .WAL file, the addon will convert the image and pack it into the scene.
If there's any desire to save the image, it will be in .PNG format.

## BSP Structure Diagram
Please note this is almost certainly not perfect, and is almost certainly missing some information regarding brushes/leaves/etc... which are not necessary for 
simply importing the map, but I used this when making this plugin, and I think can provide useful, digestable information, which is not easy
to find all in 1 spot these days (This is hard to view in Github, but you can download the actual SVG or drawio file in the repo here):
![Diagram](Anachronox_BSP_Structure.drawio.svg)
