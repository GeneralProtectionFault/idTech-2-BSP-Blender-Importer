# idTech 2 BSP Blender Importer
This addon is to import .BSP files directly into Blender.
Tested with Anachronox, and Quake II.

Video explaining use of addon:  
https://youtu.be/1dLkg9RjBr0

### Textures
<img width="304" height="289" alt="image" src="https://github.com/user-attachments/assets/0c2f48e4-1f52-46bb-bc6a-51b154af5cf8" />

The "Parent Levels" is for searching for the textures, *which you need to have extracted/available for the BSP version used by idTech 2 (Quake II).*
BE CAREFUL with this parent search if you change the setting.  It will recursively search EVERYTHING either in the folder of the BSP file you choose (set to 0), or 1 - 2 parent folders.
So, if you set this outside your intended folder, it will hang Blender while it searches everything.

Quake II has BSPs in the game directory within subfolders.  However, the BSP files and textures you will extract from the PAK
files will need to be shared among those.  I recommend extracting to the main game folder, and then if you need to find the textures
for a map like "chaos," which is in a folder *within* the main game folder, you set the parent search to get to that main directory.

#### Alternative to texture search headache
If you prefer (and you very well may), simply extrct the PAK files containing the textures and BSPs all into one separate folder.
If you do this, note that there are some BSPs *not in the PAK files*, already in the game folder you'll want to copy in there as well.
But, once you've copied everything to that folder, just leave the "Parent Levels" setting to 0, and it will find all the textures.
Just make sure you leave the little subfolders that come out of the PAK files (like e1u1, e1u2, etc...)...as they are part of the path
that is referenced in the BSP files.  Ergo, remove those, the addon won't find them.  However, this way, everything is searching "down" and 
no need to figure out how many folders up you have to search.

This parent search option is potentially more trouble than it's worth, but it was a (limited success? :-P) attempt to limit the need to understand
this file structure stuff to import the model.

### Optional Lightmaps
Also in the aboe screenshot, the lightmaps options are indicated.  These models start at full brightness, and lightmaps are included in a lump of the file
(literally just an unbroken byte lump of RGB values).  These will be parsed and a large atlas texture will be created, comprised of all the lightmaps.
A few things to be aware of with these...  As the original game engine would usually have varying amounts of lighting at runtime, applying these fully
can have varying results, such as being way too dark if there was a lot of lighting.  Conversely, they can also affect the color of the textures.
TLDR, in some cases, it makes sense to apply them, but not others, and still others, you may want them, but not at full influence.
This is the purpose for the lightmap influence slider.  It will be a material setting that affects a mix shader to tweak the influence as desired.
One other thing is that Blender will default to linear interpolation of pixels.  This can give the look of a sort of subtle "border" on some faces, so this isn't perfect.
We can turn the interpolation off by setting the interpolation in the image node to "Closest," but this isn't how the original game engine would have handled it either,
as this creates a stark, pixelated separation.

As an aside, this effect is amplified because the lightmaps have 1 pixel for every 16x16 pixels of the mesh face they apply to (lighting was not required at pixel level).

This addon does not (yet, at least) attempt to import models and/or entities referred to by the .BSP file.
There is currently an option to add en empty for each entity that has an orign/location to put it at, to at least show the information.

![image](https://github.com/user-attachments/assets/cc4cce35-0cda-4902-8784-7d7410ecdd0e)
<img width="2049" height="873" alt="image" src="https://github.com/user-attachments/assets/6dc978a6-7e9d-46e9-8c4e-aede1a8319e7" />


### .WAL images
Support has been added for .wal images, commonly used in Quake II.
These, along with other files, need to be extracted from the Quake II PAK files.
This tool will make that easy: https://github.com/GeneralProtectionFault/PAKExtract

Note that Blender does not support .WAL files.  The addon will convert the image to PNG and pack it into the scene.

## BSP Structure Diagram
Please note this is almost certainly not perfect, and is almost certainly missing some information regarding brushes/leaves/etc... which are not necessary for 
simply importing the map, but I used this when making this plugin, and I think can provide useful, digestable information, which is not easy
to find all in 1 spot these days (This is hard to view in Github, but you can download the actual SVG or drawio file in the repo here):
![Diagram](Anachronox_BSP_Structure.drawio.svg)
