import json
import os
from pathlib import Path

def scan_abi_files():
    abi_dir = Path("ABI")
    
    # 遍历ABI目录下的所有文件
    for file_path in abi_dir.glob("*.ABI"):
        try:
            # 读取并解析ABI文件
            with open(file_path, 'r', encoding='utf-8') as f:
                abi_data = json.load(f)
            
            # 查找mint函数
            mint_functions = []
            for item in abi_data:
                if isinstance(item, dict) and item.get('name') == 'mint':
                    mint_functions.append(item)
            
            # 如果找到mint函数，打印信息
            if mint_functions:
                print(f"\n文件: {file_path.name}")
                print("找到的mint函数:")
                for func in mint_functions:
                    print("\n函数结构:")
                    print(json.dumps(func, indent=2, ensure_ascii=False))
                print("-" * 80)
                
        except Exception as e:
            print(f"处理文件 {file_path.name} 时出错: {str(e)}")

if __name__ == "__main__":
    print("开始扫描ABI文件中的mint函数...")
    scan_abi_files()
    print("\n扫描完成!") 