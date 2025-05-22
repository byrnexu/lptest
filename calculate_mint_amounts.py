import math
from decimal import Decimal, getcontext

# 设置Decimal精度
getcontext().prec = 28

def calculate_mint_amounts(
    amount0_desired: float,
    amount1_desired: float,
    current_price: float,
    price_lower: float,
    price_upper: float,
    fee: float = 0.003  # 默认0.3%手续费
) -> tuple[float, float]:
    """
    计算在Uniswap V3中mint时实际需要提供的token0和token1数量
    
    参数:
    amount0_desired: 期望提供的token0数量
    amount1_desired: 期望提供的token1数量
    current_price: 当前价格 (token1/token0)
    price_lower: 价格区间下限
    price_upper: 价格区间上限
    fee: 手续费比例 (默认0.3%)
    
    返回:
    (amount0, amount1): 实际需要提供的token0和token1数量
    """
    # 转换为Decimal以提高精度
    amount0_desired = Decimal(str(amount0_desired))
    amount1_desired = Decimal(str(amount1_desired))
    current_price = Decimal(str(current_price))
    price_lower = Decimal(str(price_lower))
    price_upper = Decimal(str(price_upper))
    fee = Decimal(str(fee))
    
    # 计算价格区间
    if current_price <= price_lower:
        # 当前价格低于区间，只需要提供token0
        amount0 = amount0_desired
        amount1 = Decimal('0')
    elif current_price >= price_upper:
        # 当前价格高于区间，只需要提供token1
        amount0 = Decimal('0')
        amount1 = amount1_desired
    else:
        # 当前价格在区间内，需要同时提供token0和token1
        # 计算最优比例：使用价格区间的几何平均数
        optimal_ratio = (price_lower * price_upper).sqrt()
        
        # 计算实际需要提供的数量
        # 首先尝试使用amount0_desired计算
        amount0 = amount0_desired
        amount1 = amount0 * optimal_ratio
        
        # 如果计算出的amount1超过期望值，则使用amount1_desired计算
        if amount1 > amount1_desired:
            amount1 = amount1_desired
            amount0 = amount1 / optimal_ratio
        
        # 验证计算出的数量是否在价格区间内
        actual_price = amount1 / amount0
        if actual_price < price_lower or actual_price > price_upper:
            # 如果不在区间内，调整到区间边界
            if actual_price < price_lower:
                amount0 = amount0_desired
                amount1 = amount0 * price_lower
            else:
                amount1 = amount1_desired
                amount0 = amount1 / price_upper
    
    # 考虑手续费
    amount0 = amount0 * (Decimal('1') - fee)
    amount1 = amount1 * (Decimal('1') - fee)
    
    return float(amount0), float(amount1)

def get_valid_float_input(prompt: str) -> float:
    """
    获取有效的浮点数输入
    
    参数:
    prompt: 输入提示
    
    返回:
    有效的浮点数
    """
    while True:
        try:
            value = input(prompt).strip()
            # 移除可能的反斜杠
            value = value.replace('\\', '')
            return float(value)
        except ValueError:
            print("输入无效，请输入一个有效的数字")

def main():
    # 示例使用
    print("Uniswap V3 Mint Amount Calculator")
    print("-" * 40)
    
    # 获取用户输入
    amount0_desired = get_valid_float_input("请输入期望提供的token0数量: ")
    amount1_desired = get_valid_float_input("请输入期望提供的token1数量: ")
    current_price = get_valid_float_input("请输入当前价格 (token1/token0): ")
    price_lower = get_valid_float_input("请输入价格区间下限: ")
    price_upper = get_valid_float_input("请输入价格区间上限: ")
    fee = get_valid_float_input("请输入手续费比例 (例如0.003表示0.3%): ")
    
    # 验证输入值的合理性
    if price_lower >= price_upper:
        print("错误：价格区间下限必须小于上限")
        return
    
    if current_price <= 0 or price_lower <= 0 or price_upper <= 0:
        print("错误：价格必须大于0")
        return
    
    if fee < 0 or fee > 1:
        print("错误：手续费比例必须在0到1之间")
        return
    
    # 计算实际需要提供的数量
    amount0, amount1 = calculate_mint_amounts(
        amount0_desired,
        amount1_desired,
        current_price,
        price_lower,
        price_upper,
        fee
    )
    
    # 输出结果
    print("\n计算结果:")
    print(f"实际需要提供的token0数量: {amount0:.6f}")
    print(f"实际需要提供的token1数量: {amount1:.6f}")
    
    # 计算并显示实际价格
    if amount0 > 0:
        actual_price = amount1 / amount0
        print(f"实际价格 (token1/token0): {actual_price:.6f}")

if __name__ == "__main__":
    main() 