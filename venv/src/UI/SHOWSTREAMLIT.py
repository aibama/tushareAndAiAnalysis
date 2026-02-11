import streamlit as st
import pandas as pd

# 创建一个示例 DataFrame
data = {
    "姓名": ["张三", "李四", "王五"],
    "年龄": [25, 30, 35],
    "职业": ["工程师", "设计师", "产品经理"]
}
df = pd.DataFrame(data)

# 使用 st.dataframe() 显示表格
st.title("使用 st.dataframe() 显示表格")
st.dataframe(df)