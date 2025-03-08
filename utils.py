import os
import glob

paths = [
    '/home/q/ART/Anachronox/BSPs/ballotine/Girder05.tga'
]


def split_path_all_parts(path):
    parts = []
    while True:
        head, tail = os.path.split(path)
        if head == path:  # Absolute path
            parts.append(head)
            break
        elif tail:
            parts.append(tail)
            path = head
        else:
            parts.append(head)
            break
    parts.reverse()
    return parts


def getfile_insensitive_from_list(potential_paths):
    # Create a dictionary to map casefolded paths to their original case
    path_dict = {path.casefold(): path for path in potential_paths}
    
    for path in potential_paths:
        if os.path.isfile(path):
            # print(f"Original path found: {path}")
            return path
        else:   # Build the path a folder at a time.  This is stupid, but otherwise we need to waste time listing the directory
            split_path = split_path_all_parts(path)
            built_path = ''
            for part in split_path:
                if os.path.exists(part):
                    built_path = os.path.join(built_path, part)
                elif os.path.exists(os.path.join(built_path, part)):
                    built_path = os.path.join(built_path, part)
                elif os.path.exists(os.path.join(built_path, part.casefold())):
                    built_path = os.path.join(built_path, part.casefold())
            return built_path
    return None  # Return None if no valid path is found

