# Gayanara - Revenue Loss Analysis

> This project demonstrates an end-to-end **Data Analytics and Business Intelligence workflow**, starting from data preparation and data modeling to visualization and business insight generation.

---

## 1. Business Understanding

### 1.1 Business Background

#### Business Overview

**Gayanara** is a fictional fashion e-commerce retail business that sells a variety of fashion products through an online retail platform. As an e-commerce business, Gayanara generates revenue primarily through completed customer orders. The business operates across different product categories, customer segments, geographic regions, payment methods, and delivery channels. The business maintains several interconnected datasets covering customer information, product information, orders, order items, and customer reviews. These datasets provide an opportunity to analyze not only overall sales performance but also the portion of revenue that fails to be realized due to unsuccessful transactions. The core business process can be illustrated as:

**Customer → Order → Order Fulfillment → Completed Transaction → Revenue**

However, not every order reaches the final stage. Some orders may be **cancelled**, while others may be **returned** after the purchase has been completed or fulfilled. These events can reduce the amount of revenue that the business ultimately realizes. Therefore, looking only at total sales or total orders may provide an incomplete picture of business performance.

#### Revenue and Revenue Loss Context

For an e-commerce retailer, revenue performance is influenced not only by the number of products sold but also by the ability to successfully convert orders into realized sales.

Consider the following simplified example:

> Gayanara receives orders worth Rp1 billion during a particular period. However, Rp100 million of those orders are cancelled or subsequently returned.

Although the business initially recorded Rp1 billion in order value, not all of that value represents revenue that can ultimately be retained by the business.

This creates an important distinction between:

* **Revenue generated from successful orders**
* **Revenue associated with cancelled orders**
* **Revenue associated with returned orders**
* **Revenue that is effectively lost as a result of unsuccessful or reversed transactions**

For this project, revenue loss is specifically defined based on **cancelled and returned orders**.

#### Why Revenue Loss Matters

Revenue loss is important because a business can experience apparently healthy sales activity while still losing a significant portion of its potential realized revenue through cancellations and returns.

For example, two product categories could generate the same gross order value:

| Category   | Order Value | Cancelled/Returned Value | Realized Revenue |
| ---------- | ----------: | -----------------------: | ---------------: |
| Category A |      Rp500M |                    Rp20M |           Rp480M |
| Category B |      Rp500M |                   Rp100M |           Rp400M |

Both categories initially generate the same order value. However, Category B experiences substantially greater revenue loss. This means that evaluating performance solely through sales volume or gross order value could hide important operational and commercial issues.

Understanding revenue loss allows Gayanara to investigate questions such as:

* Which product categories experience the highest revenue loss?
* Which products contribute the most to cancelled and returned revenue?
* Are revenue losses concentrated in particular customer segments?
* Are certain regions associated with higher cancellation or return rates?
* Are particular payment methods associated with higher cancellation rates?
* Are specific couriers associated with higher levels of returned or cancelled orders?
* How does revenue loss change over time?
* Which areas should receive further business investigation?

The objective is therefore not simply to measure how much revenue was lost, but to understand **where the loss occurs and what characteristics are associated with it**.

---

### 1.2 Business Problem

#### Problem Statement

Gayanara currently has historical transactional data containing information about customers, products, orders, order items, and reviews. However, overall sales metrics alone do not provide sufficient visibility into the amount of revenue that fails to be realized due to **cancelled and returned orders**. Cancelled and returned transactions represent situations where the value associated with an order does not ultimately contribute to retained sales revenue in the same way as successful orders. If these transactions are not analyzed separately, several important business conditions may remain hidden.

#### Specific Business Problem

The primary business problem addressed in this project is:

> **Gayanara lacks visibility into the magnitude, distribution, and characteristics of revenue loss resulting from cancelled and returned orders.**

The analysis focuses specifically on **actual historical revenue loss observed in the dataset**.

This distinction is important because those situations represent **potential or estimated revenue opportunities**, whereas cancelled and returned orders are directly observable in the available transactional data.

#### Revenue Loss Scope

Within this project, revenue loss is examined through two primary transaction outcomes:

##### 1. Cancelled Order Revenue

Revenue associated with orders whose status is classified as **cancelled**.

These transactions represent orders that did not proceed to a successful completed purchase.

The analysis investigates:

$$
Cancelled\ Revenue =
\sum Subtotal\ of\ Cancelled\ Order\ Items
$$

depending on the revenue definition established for the dataset.

##### 2. Returned Order Revenue

Revenue associated with orders whose status is classified as **returned**.

These transactions represent purchases that were subsequently returned and therefore do not represent retained sales in the same way as successfully completed orders.

The analysis investigates:

$$
Returned\ Revenue =
\sum Subtotal\ of\ Returned\ Order\ Items
$$

---

### 1.3 Business Objectives

The overall objective of this project is:

> **To analyze and quantify revenue loss associated with cancelled and returned orders at Gayanara, identify the segments and transaction characteristics where revenue loss is concentrated, and provide data-driven insights that can support targeted business investigation and decision-making.**

This objective can be divided into several specific objectives.

#### Objective 1 - Understand Revenue Loss Trends

Analyze how cancellation, return, and revenue loss change over time. This allows Gayanara to determine whether revenue loss is a persistent issue or concentrated within particular periods.

The analysis can identify:

* periods with unusually high revenue loss,
* monthly or weekly trends,
* changes in cancellation rate,
* changes in return rate,
* and whether revenue loss is increasing or decreasing relative to overall sales.

#### Objective 2 - Identify Products and Categories with High Revenue Loss

Analyze revenue loss across:

* product categories,
* sub-categories,
* brands,
* and individual products.

The objective is to identify products that:

* contribute the largest absolute amount of lost revenue,
* have high cancellation rates,
* have high return rates,
* or exhibit both high sales and high revenue loss.

#### Objective 3 - Identify Customer Segments Associated with Revenue Loss

Analyze revenue loss based on available customer characteristics, including:

* gender,
* age group,
* customer location,
* and other relevant customer attributes.

The objective is to determine whether revenue loss is disproportionately concentrated within particular customer segments. This can help Gayanara identify customer groups that may require further investigation regarding their purchasing and cancellation/return behavior.

#### Objective 4 — Identify Geographic Patterns

Analyze revenue loss by:

* province,
* city,
* and other available geographic dimensions.

The objective is to determine whether certain geographic areas contribute disproportionately to:

* cancelled revenue,
* returned revenue,
* cancellation rate,
* return rate,
* or total revenue loss.

Geographic patterns can provide useful signals for further investigation into fulfillment, delivery, customer behavior, or market-specific conditions.

### 1.4 Business Questions

To achieve the objectives above, the analysis is structured around several key business questions.

1. How much revenue does Gayanara lose from cancelled and returned orders?
2. Is revenue loss primarily associated with cancellations or returns?
3. How does revenue loss change over time?
4. Which product categories contribute the most to revenue loss?
5. Which products have the highest cancellation and return rates?
6. Which products combine high revenue contribution with high revenue loss?
7. Which customer segments contribute the most to revenue loss?
8. Are cancellation and return rates significantly different across customer segments?
9. Which provinces and cities contribute the most to cancelled and returned revenue?
10. Which geographic areas have high revenue contribution but also high revenue loss rates?
11. Which payment methods are associated with higher cancellation rates?

---

## 2. Data Preparation

### 2.1 Data Overview

The Gayanara Revenue Loss Analysis project uses five interconnected datasets representing different aspects of the e-commerce business:

| Dataset         | Role      | Description                                                        | Key Identifier                                       |
| --------------- | --------- |------------------------------------------------------------------- | ---------------------------------------------------- |
| **customers**   | Dimension | Customer demographic and registration information                  | `customer_id`                                        |
| **products**    | Dimension | Product attributes, pricing, inventory, and product classification | `product_id`                                         |
| **orders**      | Dimension      | Order-level transaction and operational information                | `order_id`                                           |
| **order_items** | Fact | Product-level details for each order                               | `item_id`, `order_id`, `product_id`                  |
| **reviews**     | Dimension | Customer reviews and ratings associated with products and orders   | `review_id`, `order_id`, `product_id`, `customer_id` |

---

### 2.2 Data Preparation Objectives

The data preparation process is performed to ensure that the datasets are suitable for reliable analysis and visualization.

The main objectives are to:

1. Ensure data quality by identifying and handling missing, inconsistent, or invalid values.
2. Standardize data types and formats so that numerical, categorical, and date fields can be analyzed correctly.
3. Validate key identifiers and relationships between tables.
4. Prevent duplicate records from distorting revenue calculations.
5. Establish consistent definitions for revenue, cancelled orders, returned orders, and revenue loss.
6. Create analytical fields required for KPI calculations.
7. Prepare a relational data structure that can be efficiently connected in Tableau.
8. Ensure that the final dataset accurately represents the business logic defined during the Business Understanding stage.

---

### 2.3 Data Profiling

Before performing transformations, the datasets are profiled to understand their structure, quality, and relationships.

The profiling process examines:

* Number of rows and columns
* Column names and data types
* Missing values
* Duplicate records
* Unique values
* Value distributions
* Minimum and maximum values
* Potentially invalid values
* Primary key uniqueness
* Foreign key consistency
* Relationships between tables

This stage is important because data quality issues identified early can prevent inaccurate revenue calculations later in the analysis.

---

#### 2.3.1 Customers Table

The `customers` table contains:

* `customer_id`
* `name`
* `email`
* `phone`
* `city`
* `province`
* `registration_date`
* `gender`
* `age_group`

The preparation focuses on ensuring that:

* `customer_id` is unique.
* `Customer` identifiers are not missing.
* `registration_date` is stored as a valid date.
* `gender` values are consistently formatted.
* `age_group` values follow a consistent classification.
* `City` and `province` names use consistent formatting.
* Duplicate `customer` records are identified and investigated.

The `customer_id` serves as the primary key for connecting customers to their orders.

---

#### 2.3.2 Products Table

The `products` table contains:

* `product_id`
* `name`
* `sub_category`
* `price_idr`
* `stock`
* `brand`
* `avg_rating`
* `category`
* `material`

The preparation focuses on ensuring that:

* `product_id` is unique.
* `price_idr` is stored as a numeric field.
* `stock` is stored as a numeric field.
* `avg_rating` is stored as a numeric field.
* `Category` and `sub_category` values are standardized.
* `Brand` names are consistently formatted.
* `Product` names are checked for duplicates or inconsistent representations.
* Negative or otherwise invalid numerical values are investigated.

The `product_id` serves as the primary key used to connect product information to `order_items`.

---

#### 2.3.3 Orders Table

The `orders` table is the main order-level transactional dataset.

It contains:

* `order_id`
* `customer_id`
* `order_date`
* `total_amount_idr`
* `shipping_city`
* `shipping_province`
* `shipping_cost_idr`
* `payment_method`
* `order_status`
* `promo_code`
* `courier`
* `discount_amount_idr`

The preparation of this table is particularly important because `order_status` determines whether an order contributes to realized revenue or revenue loss.

The preparation focuses on ensuring that:

* `order_id` should uniquely identify each order
* `customer_id` Each order should be associated with a valid customer
* `order_date` field is converted into a valid date format
* Standardize `order_status` values are reviewed and standardized to ensure consistent classification
* `total_amount_idr`, `shipping_cost_idr`, and `discount_amount_idr` are checked for appropriate numeric data types
* Categorical fields such as `payment_method`, `promo_code`, `courier`, `shipping_city`, and `shipping_province` are standardized to ensure that differences in capitalization, spacing, or naming do not create artificial categories

---

#### 2.3.4 Order Items Table

The `order_items` table provides the product-level details of each transaction., it contains:

* `item_id`
* `order_id`
* `product_id`
* `quantity`
* `unit_price_idr`
* `subtotal_idr`

This table is particularly important for calculating product-level revenue and revenue loss.

The preparation focuses on ensuring that:

* Each `item_id` should uniquely identify an order_item record
* Every `order_id` in `order_items` should correspond to an order in the `orders` table
* Every `product_id` in `order_items` should correspond to a valid product in the `products` table
* The `quantity` field is checked to ensure that values are numeric and logically valid
* `unit_price_idr` is checked to ensure that it contains valid numeric values.
* `sub_total_idr` field is checked to ensure that values are numeric and logically valid. The validated `subtotal_idr` is then used as the primary basis for product-level revenue analysis where appropriate.

---

#### 2.3.5 Reviews Table

The `reviews` table contains:

* `review_id`
* `order_id`
* `product_id`
* `customer_id`
* `rating`
* `review_text`
* `review_date`
* `helpful_count`

Although reviews are not the primary source for revenue calculation, they can provide additional context for investigating product performance.

The preparation includes:

* Validating unique `review_id`
* Validating `order_id`
* Validating `product_id`
* Validating `customer_id`
* Standardizing `rating`
* Converting `review_date` to a valid date
* Checking missing values
* Checking rating ranges
* Identifying duplicate reviews

---

### 2.4 Handling Missing Values

Missing values are assessed according to their business meaning rather than automatically removed.

Different fields require different approaches.

For example:

* A missing `promo_code` may represent an order without a promotion rather than missing information.
* A missing `phone` number may not affect revenue analysis.
* A missing `customer_id` in an order may represent a referential integrity issue.
* A missing `product_id` in `order_items` may prevent product-level analysis.
* A missing `order_status` can significantly affect revenue classification and therefore requires investigation.

Therefore, missing-value treatment is determined based on the analytical role of each field.

This prevents unnecessary deletion of valid business records while protecting critical calculations from incomplete data.

---

### 2.5 Handling Duplicate Records

Duplicate records are investigated at both the table and transaction levels.

The primary keys used for validation include:

| Table       | Primary Key   |
| ----------- | ------------- |
| Customers   | `customer_id` |
| Products    | `product_id`  |
| Orders      | `order_id`    |
| Order Items | `item_id`     |
| Reviews     | `review_id`   |

Duplicates are particularly important in the `orders` and `order_items` tables because duplicate transactions could result in overstated revenue.

The objective is not simply to remove every repeated value, because repeated `order_id` values in `order_items` are expected when one order contains multiple products.

For example:

```text
order_id = 1001
    ├── Product A
    ├── Product B
    └── Product C
```

This is a valid one-to-many relationship rather than duplicate data.

Therefore, duplicate detection is performed based on the appropriate grain of each table.

---

### 2.6 Data Type Standardization

Consistent data types are established before analysis.

#### Date fields

Converted to date format:

* `registration_date`
* `order_date`
* `review_date`

#### Numeric fields

Converted to numeric format:

* `price_idr`
* `stock`
* `avg_rating`
* `total_amount_idr`
* `shipping_cost_idr`
* `discount_amount_idr`
* `quantity`
* `unit_price_idr`
* `subtotal_idr`
* `rating`
* `helpful_count`

#### Categorical fields

Standardized as dimensions:

* `gender`
* `age_group`
* `category`
* `sub_category`
* `brand`
* `material`
* `payment_method`
* `order_status`
* `promo_code`
* `courier`
* `city`
* `province`

---

### 2.7 Data Integration

After individual tables have been cleaned and validated, the datasets are connected based on their relational keys.

The primary relationships are:

![Data Relationship Preview](images/data_relation.png)

This relational structure allows transaction-level revenue loss to be analyzed against multiple business dimensions without unnecessarily duplicating data.

| Dimension       | Key          | Cardinality |
| --------------- | ------------ | ----------- |
| **customers**   | `customer_id`| 1:*         |
| **products**    | `product_id` | 1:*         | 
| **orders** | `order_id`   | 1:*         |
| **reviews**     | `order_id`   | 1:*         |

---

## 5. Dashboard Overview

[Link to tableau dashboard](https://public.tableau.com/views/Gayanara_dashboard/Overview?:language=en-US&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link)



![Dashboard Preview](images/Overview.png)

## 6. Key Findings

### Finding 1 - Profitability reached a major peak around early 2020




---

### Finding 2 - Revenue is strongly concentrated in a small number of product categories

![Revenue By Category](images/rev_cat.png)

| Category                      | Revenue  | Profit Margin |
| ------------------------------| ---------| --------------|
| Computers                     | $19.30 M | 58.4%        |
| Home Appliances               | $10.80 M | 58.3%        |
| Cameras and camcorders        | $6.52 M  | 60.1%        |
| Cell phones                   | $6.18 M  | 56.6%        |
| TV and Video                  | $5.93 M  | 59.7%        |
| Audio                         | $3.17 M  | 57.7%        |
| Music, Movies and Audio Books | $3.13 M  | 61.0%        |
| Games and Toys                | $0.72 M  | 54.7%        |


**Insight:**   
`Computers` is the largest revenue contributor at **$19.30M (34.6%)**, followed by `Home Appliances` at **$10.80M (19.4%)**. Together, these two categories account for approximately **54%** of total revenue, indicating that overall sales performance is highly influenced by their performance. Meanwhile, `Cameras and camcorders`, `Cell phones`, and `TV and Video` each contribute approximately **10–12%**, providing additional but smaller revenue streams. At the lower end, Games and Toys contributes only **1.3%**, making it the smallest revenue-generating category.

Profit margins across product categories range from **54.7% to 61.0%**, indicating relatively consistent profitability across the portfolio. `Music, Movies and Audio Books` records the highest margin at **61.0%**, followed by `Cameras and camcorders` at **60.1%** and `TV and Video` at **59.7%**. Meanwhile, `Games and Toys` has the lowest margin at **54.7%**.


**Why it matters**:   
`Computers` and `Home Appliances` represents significant source of both revenue and profit. Together these categories contributes a substantial portion of the company's overall financial performance. Because a substantial portion of company revenue and estimated profit comes from these categories, changes in its sales performance can have a meaningful impact on overall business results. From a business perspective, management needs to monitor these categories not only in terms of sales growth but also margin stability, inventory availability, product mix, and demand trends to ensure that growth does not come at the expense of profitability.

On the other hand, the revenue distribution suggests that management should simultaneously protect the performance of the company's major revenue drivers while investigating growth opportunities and underlying performance factors in lower-contributing categories.

The high profit margin of `Music, Movies and Audio Books` indicates that the category generates a relatively large amount of profit from each dollar of revenue. However, its relatively small revenue contribution limits its impact on the company's total profit. From a business perspective, this creates a potential growth opportunity. If the company can increase sales in this category while maintaining its current margin level, the category could make a larger contribution to overall profitability. Management could therefore investigate whether the category's relatively low revenue is driven by limited product assortment, lower customer demand, distribution reach, or sales volume.

The low contribution of `Games and Toys` to both revenue and profit margin creates a need to understand the underlying causes of the category's performance before deciding how it should be managed. If the performance is caused by limited demand, the company may need to reconsider its product strategy. If it is caused by limited assortment, distribution, or promotional exposure, there may be opportunities to improve performance. The key business consideration is therefore whether the category represents a growth opportunity or a relatively low-priority segment based on its potential and underlying economics.

---

### Finding 3 - The channel mix indicates different roles within the revenue portfolio

![Revenue By Channel](images/rev_chan.png)

**Insight:**   
The `Offline` sales is the company's dominant revenue channel, generating approximately **$44.35M** or **79.5%** of total revenue, compared with **$11.40M** or **20.5%** from `online` transactions. This means the company currently relies heavily on its `offline` channel as its primary revenue engine, with `offline` revenue approximately 3.9 times larger than `online` revenue.

**Why It Matters**:   
The strong concentration of revenue in the `offline` channel means that `offline` performance has a substantially greater impact on the company's overall financial performance. A **10%** change in `offline` revenue would represent approximately **$4.44M**, compared with **$1.14M** for an equivalent change in `online` revenue. At the same time, the **$11.40M** contribution from `online` transactions indicates that digital sales already represent a meaningful component of the company's revenue portfolio. Therefore, channel performance should be evaluated not only based on revenue contribution, but also in terms of profitability, customer behavior, transaction volume, and operating economics to understand the role and business value of each channel.

---

### Finding 4 - The United States is the dominant profit market

![Profit By Country Preview](images/prof_count.png)

**Insight:**   
The company generated approximately **$25.99M** in profit across eight countries, with `the United States` contributing **$13.92M** or **53.6%** of total profit. This makes the `US` the company's dominant geographic profit engine and indicates a significant concentration of profitability in a single market. The `United Kingdom`, `Germany`, and `Canada` form a meaningful secondary profit base, collectively contributing approximately **30.6%** of total profit. Meanwhile, `Australia`, `Italy`, `the Netherlands`, and `France` each contribute less than **5%** individually.

Profit margins across the eight markets are remarkably consistent, ranging from **58.26%** in `Canada` to **59.24%** in `Australia`, representing a relatively narrow spread of approximately **0.98** percentage points. `Australia` records the highest observed profit margin at **59.24%**, followed by France at **58.98%** and `the Netherlands` at **58.93%**. Meanwhile, `Canada` records the lowest margin at **58.26%**. Despite these differences, the relatively narrow margin range indicates that geographic differences in absolute profit are not primarily explained by substantial variations in margin. This becomes particularly evident when comparing `the United States` and `Australia`. `The United States` generates approximately **$13.92M** in profit, compared with **$1.24M** in `Australia`, despite their margins being relatively close at **58.58%** and **59.24%**, respectively. This suggests that business scale and revenue volume play a much larger role in determining absolute profit contribution than small differences in margin.

**Why It Matters:**   
The concentration of profit in the `United States` means that its performance has a substantial impact on overall company profitability. At the same time, absolute profit alone does not indicate market efficiency or growth potential. Further analysis combining country, revenue, profit margin, product category, channel, and time trends is required to understand the underlying drivers of geographic profitability.

---

## 7. Strategic Recommendations

### 7.1 Product Category Strategy

1. `Computers` and `Home Appliances` should remain key priorities because they collectively generate approximately **54% of total revenue** and represent a substantial share of estimated profit. Management should focus on maintaining product availability, optimizing inventory, monitoring product-level profitability, and developing targeted promotions. Because of their large revenue base, relatively small improvements in these categories can have a meaningful impact on overall business performance. For example, a **10%** increase in Computers revenue at the current margin would represent approximately **$1.93M in additional revenue** and around **$1.13M in additional profit**.

2. `Cameras and camcorders`, `TV and Video`, and `Music, Movies and Audio Books` demonstrate relatively strong profit margins. The company should explore opportunities to increase their revenue contribution through broader product assortment, targeted marketing, cross-selling, product bundling, and improved channel exposure while maintaining margin discipline. The objective is to convert strong category-level profitability into greater absolute profit contribution.

3. `Cell Phones` generates approximately **$6.18M in revenue** but has a comparatively lower profit margin of **56.58%**. Rather than focusing exclusively on increasing sales volume, management should investigate pricing, discounting, product mix, and brand-level profitability. Cross-selling accessories and complementary products can also increase revenue and profit per transaction. A 1 percentage-point improvement in margin on the current revenue base would represent approximately **$61.8K in additional profit**, assuming revenue remains constant.

4. `Games and Toys` has the lowest revenue and lowest profit margin in the sales portfolio. Before making major portfolio decisions, management should investigate the underlying drivers of its performance, including sales volume, SKU availability, pricing, promotional exposure, inventory turnover, and seasonality. The objective is to determine whether the category represents an opportunity for improvement or should receive a lower level of strategic investment.

5. The company can increase customer basket value by creating complementary product bundles across categories. This strategy can increase revenue per transaction while reducing reliance on customer acquisition as the sole driver of revenue growth. Examples include:

    - Computers + accessories
    - Smartphones + accessories
    - TVs + audio equipment
    - Cameras + memory cards and accessories

---

### 7.2 Sales Channel Strategy

The company's revenue is currently highly concentrated in the offline channel, which contributes approximately 79.5% of total revenue, while the online channel contributes 20.5%. Therefore, the strategic priority should not be to replace the offline channel with online, but to protect the existing offline revenue base while developing online as a scalable growth channel.

1. The company should protect and optimize its offline revenue engine because changes in offline performance have a substantially larger impact on total revenue. Operational initiatives should focus on maintaining store productivity, product availability, customer experience, and performance across locations.

2. The company should develop the online channel as a growth engine. With approximately $11.40M in revenue, online sales already represent a meaningful part of the business and provide a foundation for further digital growth. However, online expansion should be evaluated based on profitability and customer economics rather than revenue growth alone.

3. The company should adopt an omnichannel strategy that connects online and offline customer journeys. Initiatives such as Click & Collect, Ship From Store, unified loyalty programs, online-to-offline engagement, and offline-to-online customer acquisition can allow both channels to complement rather than compete with each other.

4. Management should establish channel-level performance monitoring covering revenue, profit, margin, AOV, customer acquisition cost, conversion rate, repeat purchase, and customer lifetime value. This would enable the company to distinguish genuine incremental online growth from revenue that is simply shifting from offline to online.

---

### 7.3 Geographic Strategy

Geographic strategy should focus on protecting the United States as the company's core profit engine while developing secondary markets through sustainable, margin-conscious growth. Given the relatively narrow 58–59% profit margin range across countries, differences in absolute profit appear to be driven more by business scale than by major margin variations. Therefore, management should prioritize profitable revenue growth, maintain margin discipline, investigate the drivers behind high-margin markets such as Australia, France, and the Netherlands, and strengthen the performance of meaningful secondary markets such as the UK, Germany, and Canada.

---
