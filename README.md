Olist E-Commerce Data Visualization Dashboard
=============================================

This project is a Streamlit-based interactive dashboard built on the Olist
Brazilian E-Commerce dataset. It focuses on exploratory data analysis and
visualization of product categories, revenue concentration, pricing behavior,
and temporal trends.

The project was developed as part of an academic data visualization assignment
and emphasizes clarity, interpretability, and clean analytical structure.


Key Features
------------
• Multi-page Streamlit application
• Top-N product category analysis by revenue
• Average item price per category
• Revenue share of top categories vs all others
• Orders and revenue trends over time (monthly / weekly)
• Clear separation between data loading, aggregation, and visualization


Project Structure
-----------------
main.py        – Streamlit entry point and navigation
page_1.py      – Product category revenue & pricing analysis
page_2.py      – Orders and revenue over time
page_3–6.py    – Reserved for future extensions
data/          – Olist CSV datasets


Dashboard Pages
---------------
Page 1:
Top product categories by total revenue with:
• Bar chart (revenue)
• Line chart (average price)
• Pie chart (revenue share)

Page 2:
Orders and revenue trends over time using dual-axis line charts


Dataset
-------
Olist Brazilian E-Commerce Public Dataset
Includes orders, order items, products, categories, and timestamps.
Category names are optionally translated to English.


Installation & Run
------------------
1. Clone repository:
   git clone https://github.com/malachiweiss1/visualization_Malachi_Ohad.git

2. Install dependencies:
   pip install -r requirements.txt

3. Run the app:
   streamlit run main.py


Design Goals
------------
• Visual clarity over complexity
• Interpretable business insights
• Scalable structure for future analysis
• Academic-quality presentation


Author
------
Malachi Weiss
Ohad Ashkenazi
M.Sc. Data Science – Visualization Course Project
