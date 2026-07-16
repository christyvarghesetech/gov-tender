import zipfile
import re
import os

def scan_zip(zip_path, is_nested=False):
    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('.class') and 'AuthenticationFactor.class' in name:
                print(f"=== Strings in {name} ===")
                try:
                    class_bytes = z.read(name)
                    ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
                    decoded = sorted(set([s.decode('utf-8', errors='ignore') for s in ascii_strings]))
                    for s in decoded:
                        if len(s) > 2 and '/' not in s and '(' not in s and ';' not in s:
                            print(f"  {s}")
                except Exception as e:
                    print(f"Error reading {name}: {e}")
            elif name.endswith('.jar') and not is_nested:
                try:
                    nested_data = z.read(name)
                    temp_name = 'temp_sec_find.jar'
                    with open(temp_name, 'wb') as f:
                        f.write(nested_data)
                    scan_zip(temp_name, is_nested=True)
                    os.remove(temp_name)
                except Exception:
                    pass

def main():
    scan_zip('esignet/esignet-service.jar')

if __name__ == '__main__':
    main()
