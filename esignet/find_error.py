import zipfile
import re
import os

def main():
    jar_path = 'esignet/esignet-service.jar'
    print(f"Searching in {jar_path}...")
    
    with zipfile.ZipFile(jar_path, 'r') as z:
        # Check files inside BOOT-INF/classes
        for name in z.namelist():
            if name.endswith('.class'):
                try:
                    content = z.read(name)
                    if b'invalid_client_id' in content:
                        print(f"Found in classes: {name}")
                except Exception:
                    pass
                    
        # Check nested jars
        for name in z.namelist():
            if name.endswith('.jar'):
                try:
                    nested_jar_data = z.read(name)
                    # Write to temp file to read with zipfile
                    temp_name = 'temp_nested.jar'
                    with open(temp_name, 'wb') as f:
                        f.write(nested_jar_data)
                    
                    with zipfile.ZipFile(temp_name, 'r') as nz:
                        for nname in nz.namelist():
                            if nname.endswith('.class'):
                                try:
                                    ncontent = nz.read(nname)
                                    if b'invalid_client_id' in ncontent:
                                        print(f"Found in {name} -> {nname}")
                                except Exception:
                                    pass
                    os.remove(temp_name)
                except Exception as e:
                    print(f"Error checking {name}: {e}")

if __name__ == '__main__':
    main()
