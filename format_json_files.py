import os
import json
import glob
import sys

def format_json_file(file_path):
    """格式化单个JSON文件"""
    try:
        # 读取JSON文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 解析JSON内容
        data = json.loads(content)
        
        # 使用美观的格式化选项重新写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, 
                     indent=4,           # 使用4个空格缩进
                     ensure_ascii=False, # 允许非ASCII字符
                     sort_keys=False)    # 保持原始键的顺序
        
        print(f"Successfully formatted: {file_path}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in {file_path}: {str(e)}")
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return False

def format_directory(directory):
    """格式化目录下的所有JSON文件"""
    # 检查目录是否存在
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist!")
        return
    
    # 获取目录下所有的JSON文件
    json_files = glob.glob(os.path.join(directory, "*.json"))
    
    if not json_files:
        print(f"No JSON files found in directory: {directory}")
        return
    
    print(f"Found {len(json_files)} JSON files in {directory}")
    
    # 处理每个JSON文件
    success_count = 0
    for json_file in json_files:
        if format_json_file(json_file):
            success_count += 1
    
    print(f"\nFormatting completed!")
    print(f"Successfully formatted: {success_count}/{len(json_files)} files")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python format_json_files.py <directory_path>")
        sys.exit(1)
    
    directory = sys.argv[1]
    print(f"Processing JSON files in directory: {directory}")
    format_directory(directory) 