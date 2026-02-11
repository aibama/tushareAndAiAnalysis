# 计算每个用户的盈利金额
def calculate_user_profit(cost_per_user, purchase_day, days_used, membership_duration):
    actual_days = min(membership_duration - purchase_day + 1, days_used)
    profit = (cost_per_user * actual_days / membership_duration)
    return profit

# 计算总的盈利金额
def calculate_total_profit(user_data):
    cost_per_user = 20
    cost_total = 40
    membership_duration = 30
    total_profit = 0

    for purchase_day, days_used in user_data:
        profit = calculate_user_profit(cost_per_user, purchase_day, days_used, membership_duration)
        total_profit += profit

    total_profit -= cost_total

    return total_profit

# 用户数据，每个元组表示用户的购买时间和实际使用天数
user_data = [(5, 26), (10, 21), (15, 16), (20, 11), (25, 6)]

# 计算每个用户的盈利金额
user_profits = []
for purchase_day, days_used in user_data:
    profit = calculate_user_profit(20, purchase_day, days_used, 30)
    user_profits.append(profit)

# 计算总的盈利金额
total_profit = calculate_total_profit(user_data)

print("每个用户的盈利金额分别为：", user_profits, "人民币")
print("总盈利金额为：", total_profit, "人民币")