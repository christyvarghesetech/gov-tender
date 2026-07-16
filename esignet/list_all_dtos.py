import zipfile
import os

def scan_zip(zip_path, is_nested=False):
    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('.class') and 'io/mosip/esignet/core/dto' in name:
                print(f"DTO Class: {name}")
            elif name.endswith('.jar') and not is_nested:
                try:
                    nested_data = z.read(name)
                    temp_name = 'temp_list.jar'
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
