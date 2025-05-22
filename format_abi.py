import json
import os
import glob

def format_abi_file(file_path):
    try:
        # 读取文件内容
        with open(file_path, 'r') as f:
            content = f.read()
        
        # 解析JSON
        abi_data = json.loads(content)
        
        # 格式化JSON并写回文件
        with open(file_path, 'w') as f:
            json.dump(abi_data, f, indent=4)
        
        print(f"Successfully formatted {file_path}")
    except Exception as e:
        print(f"Error formatting {file_path}: {str(e)}")

def main():
    # 获取当前目录下所有.ABI文件
    abi_files = glob.glob("*.ABI")
    
    if not abi_files:
        print("No .ABI files found in current directory")
        return
    
    # 处理每个文件
    for file_name in abi_files:
        format_abi_file(file_name)

if __name__ == "__main__":
    main() 