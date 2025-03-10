This addon is to import .BSP files directly into Blender.
Tested with Anachronox, but format should be the same as Quake II.
However, .WAL image support is not yet implemented, but planned so long as I can Python-ify that.

Currently, addon will simply search all the files with appropriate extensions within the working directory,
so make sure all textures that the .BSP file needs/refers to are somewhere within the folder the .BSP file 
was opened from.

This addon does not (yet, at least) attempt to import models and/or entities referred to by the .BSP file.

![image](https://github.com/user-attachments/assets/2924d68a-5fee-47fb-8504-c0fccf3096ce)
