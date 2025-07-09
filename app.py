# === app.py ===
import streamlit as st
import pandas as pd
from analysis import analyze_graphs, analyze_error_hourly_spread
from importdata import load_data_from_csv
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 API Telemetry Diagnostics")

if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = {}

if "rendered_analysis_buttons" not in st.session_state:
    st.session_state["rendered_analysis_buttons"] = set()

df = load_data_from_csv("api_telemetry_2_months.xlsx")

# Sidebar filters
st.sidebar.header("📌 Filter Options")
service_options = df['service_name'].dropna().unique().tolist()
endpoint_options = df['endpoint'].dropna().unique().tolist()
region_options = df['region'].dropna().unique().tolist()

selected_services = st.sidebar.multiselect("🛠 Service Name", sorted(service_options))
selected_endpoints = st.sidebar.multiselect("📍 Endpoint", sorted(endpoint_options))
selected_regions = st.sidebar.multiselect("🌎 Region", sorted(region_options))
status_toggle = st.radio("✅ Choose Status to Visualize", ["Success", "Failure"])

# Date input for periods
st.sidebar.markdown("---")
st.sidebar.subheader("🗓️ Period 1")
start_date_1 = st.sidebar.date_input("Start Date 1")
end_date_1 = st.sidebar.date_input("End Date 1")

st.sidebar.subheader("🗓️ Period 2")
start_date_2 = st.sidebar.date_input("Start Date 2")
end_date_2 = st.sidebar.date_input("End Date 2")

start_date_1 = pd.to_datetime(start_date_1).tz_localize("UTC")
end_date_1 = pd.to_datetime(end_date_1).tz_localize("UTC") + pd.Timedelta(days=1)
start_date_2 = pd.to_datetime(start_date_2).tz_localize("UTC")
end_date_2 = pd.to_datetime(end_date_2).tz_localize("UTC") + pd.Timedelta(days=1)

if start_date_1 >= end_date_1 or start_date_2 >= end_date_2:
    st.error("Start date must be before end date.")
    st.stop()

# Apply filters
if selected_services:
    df = df[df['service_name'].isin(selected_services)]
if selected_endpoints:
    df = df[df['endpoint'].isin(selected_endpoints)]
if selected_regions:
    df = df[df['region'].isin(selected_regions)]

df1 = df[(df['timestamp'] >= start_date_1) & (df['timestamp'] < end_date_1)].copy()
df2 = df[(df['timestamp'] >= start_date_2) & (df['timestamp'] < end_date_2)].copy()

def plot_counts_by_day(df_filtered, status):
    df_filtered = df_filtered[df_filtered['status'].str.lower() == status.lower()]
    df_filtered["date"] = df_filtered["timestamp"].dt.date
    return df_filtered.groupby("date").size().reset_index(name="count")

# Generate charts
df1_chart = plot_counts_by_day(df1, status_toggle)
df2_chart = plot_counts_by_day(df2, status_toggle)

fig1 = px.line(df1_chart, x="date", y="count", title="Period 1", markers=True)
fig2 = px.line(df2_chart, x="date", y="count", title="Period 2", markers=True)

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig1, use_container_width=True)
with col2:
    st.plotly_chart(fig2, use_container_width=True)

# GPT Compare (Main LLM Analysis)
if st.button("🧠 Analyze with LLM"):
    fig1.write_image("temp1.png")
    fig2.write_image("temp2.png")
    with st.spinner("Analyzing..."):
        result = analyze_graphs(
            image1_path="temp1.png",
            image2_path="temp2.png",
            status=status_toggle,
            start_date_1=start_date_1,
            end_date_1=end_date_1,
            start_date_2=start_date_2,
            end_date_2=end_date_2,
            df1=df1,
            df2=df2
        )
    st.session_state["llm_result"] = result

if "llm_result" in st.session_state:
    st.markdown("### 🧠 LLM Summary")
    st.write(st.session_state["llm_result"])

# === 🔍 Per-Day, Per-Error Comparison Drilldown ===
st.markdown("## 🔍 Single Day Error Comparison Drilldown")

all_dates_1 = sorted(df1['timestamp'].dt.date.unique())
all_dates_2 = sorted(df2['timestamp'].dt.date.unique())

col1, col2 = st.columns(2)
with col1:
    selected_date_1 = st.selectbox("Select a date from Period 1", all_dates_1)
with col2:
    selected_date_2 = st.selectbox("Select a date from Period 2", all_dates_2)

filt_df1 = df1[(df1['timestamp'].dt.date == selected_date_1) & (df1['status'].str.lower() == status_toggle.lower())]
filt_df2 = df2[(df2['timestamp'].dt.date == selected_date_2) & (df2['status'].str.lower() == status_toggle.lower())]

if filt_df1.empty or filt_df2.empty:
    st.info("No matching data for selected dates.")
else:
    st.markdown(f"### 📊 Error Comparison: {selected_date_1} vs {selected_date_2}")
    p1_counts = filt_df1['response_status_code'].value_counts()
    p2_counts = filt_df2['response_status_code'].value_counts()
    all_codes = sorted(set(p1_counts.index).union(set(p2_counts.index)))

    comparison_data = []
    for code in all_codes:
        comparison_data.append({
            "Error Code": code,
            "Period 1 Count": p1_counts.get(code, 0),
            "Period 2 Count": p2_counts.get(code, 0)
        })
    comparison_df = pd.DataFrame(comparison_data)
    st.dataframe(comparison_df)

    for row in comparison_df.itertuples():
        with st.expander(f"🔎 Error {row._1} Comparison"):
            col1, col2 = st.columns(2)

            with col1:
                df1_hourly = filt_df1[filt_df1['response_status_code'] == row._1].copy()
                df1_hourly['hour'] = df1_hourly['timestamp'].dt.hour
                chart1 = px.bar(df1_hourly.groupby('hour').size().reset_index(name='count'), x='hour', y='count',
                                title=f"{selected_date_1} Error {row._1}", labels={'hour': 'Hour', 'count': 'Count'})
                st.plotly_chart(chart1, use_container_width=True)
                analysis_key = f"p1_{row._1}"
                if st.button(f"🧠 Analyze {row._1} on {selected_date_1}", key=analysis_key):
                    with st.spinner("Analyzing..."):
                        result = analyze_error_hourly_spread(df1_hourly, row._1, selected_date_1, status_toggle)
                        st.session_state["analysis_results"][analysis_key] = result
                if analysis_key in st.session_state["analysis_results"]:
                    st.write(st.session_state["analysis_results"][analysis_key])

            with col2:
                df2_hourly = filt_df2[filt_df2['response_status_code'] == row._1].copy()
                df2_hourly['hour'] = df2_hourly['timestamp'].dt.hour
                chart2 = px.bar(df2_hourly.groupby('hour').size().reset_index(name='count'), x='hour', y='count',
                                title=f"{selected_date_2} Error {row._1}", labels={'hour': 'Hour', 'count': 'Count'})
                st.plotly_chart(chart2, use_container_width=True)
                analysis_key = f"p2_{row._1}"
                if st.button(f"🧠 Analyze {row._1} on {selected_date_2}", key=analysis_key):
                    with st.spinner("Analyzing..."):
                        result = analyze_error_hourly_spread(df2_hourly, row._1, selected_date_2, status_toggle)
                        st.session_state["analysis_results"][analysis_key] = result
                if analysis_key in st.session_state["analysis_results"]:
                    st.write(st.session_state["analysis_results"][analysis_key])

# === END ===



# # === app.py ===
# import streamlit as st
# import pandas as pd
# from analysis import analyze_graphs, analyze_error_hourly_spread
# from importdata import load_data_from_csv
# import plotly.express as px

# st.set_page_config(layout="wide")
# st.title("📊 API Telemetry Diagnostics")

# df = load_data_from_csv("api_telemetry_2_months.xlsx")

# # Sidebar filters
# st.sidebar.header("📌 Filter Options")
# service_options = df['service_name'].dropna().unique().tolist()
# endpoint_options = df['endpoint'].dropna().unique().tolist()
# region_options = df['region'].dropna().unique().tolist()

# selected_services = st.sidebar.multiselect("🛠 Service Name", sorted(service_options))
# selected_endpoints = st.sidebar.multiselect("📍 Endpoint", sorted(endpoint_options))
# selected_regions = st.sidebar.multiselect("🌎 Region", sorted(region_options))
# status_toggle = st.radio("✅ Choose Status to Visualize", ["Success", "Failure"])

# # Date input for periods
# st.sidebar.markdown("---")
# st.sidebar.subheader("🗓️ Period 1")
# start_date_1 = st.sidebar.date_input("Start Date 1")
# end_date_1 = st.sidebar.date_input("End Date 1")

# st.sidebar.subheader("🗓️ Period 2")
# start_date_2 = st.sidebar.date_input("Start Date 2")
# end_date_2 = st.sidebar.date_input("End Date 2")

# start_date_1 = pd.to_datetime(start_date_1).tz_localize("UTC")
# end_date_1 = pd.to_datetime(end_date_1).tz_localize("UTC") + pd.Timedelta(days=1)
# start_date_2 = pd.to_datetime(start_date_2).tz_localize("UTC")
# end_date_2 = pd.to_datetime(end_date_2).tz_localize("UTC") + pd.Timedelta(days=1)

# if start_date_1 >= end_date_1 or start_date_2 >= end_date_2:
#     st.error("Start date must be before end date.")
#     st.stop()

# # Apply filters
# if selected_services:
#     df = df[df['service_name'].isin(selected_services)]
# if selected_endpoints:
#     df = df[df['endpoint'].isin(selected_endpoints)]
# if selected_regions:
#     df = df[df['region'].isin(selected_regions)]

# df1 = df[(df['timestamp'] >= start_date_1) & (df['timestamp'] < end_date_1)].copy()
# df2 = df[(df['timestamp'] >= start_date_2) & (df['timestamp'] < end_date_2)].copy()

# def plot_counts_by_day(df_filtered, status):
#     df_filtered = df_filtered[df_filtered['status'].str.lower() == status.lower()]
#     df_filtered["date"] = df_filtered["timestamp"].dt.date
#     return df_filtered.groupby("date").size().reset_index(name="count")

# # Generate charts
# df1_chart = plot_counts_by_day(df1, status_toggle)
# df2_chart = plot_counts_by_day(df2, status_toggle)

# fig1 = px.line(df1_chart, x="date", y="count", title="Period 1", markers=True)
# fig2 = px.line(df2_chart, x="date", y="count", title="Period 2", markers=True)

# col1, col2 = st.columns(2)
# with col1:
#     st.plotly_chart(fig1, use_container_width=True)
# with col2:
#     st.plotly_chart(fig2, use_container_width=True)

# # GPT Compare (Main LLM Analysis)
# if st.button("🧠 Analyze with LLM"):
#     fig1.write_image("temp1.png")
#     fig2.write_image("temp2.png")
#     with st.spinner("Analyzing..."):
#         result = analyze_graphs(
#             image1_path="temp1.png",
#             image2_path="temp2.png",
#             status=status_toggle,
#             start_date_1=start_date_1,
#             end_date_1=end_date_1,
#             start_date_2=start_date_2,
#             end_date_2=end_date_2,
#             df1=df1,
#             df2=df2
#         )
#     st.session_state["llm_result"] = result

# if "llm_result" in st.session_state:
#     st.markdown("### 🧠 LLM Summary")
#     st.write(st.session_state["llm_result"])

# # === 🔍 Per-Day, Per-Error Comparison Drilldown ===
# st.markdown("## 🔍 Single Day Error Comparison Drilldown")

# all_dates_1 = sorted(df1['timestamp'].dt.date.unique())
# all_dates_2 = sorted(df2['timestamp'].dt.date.unique())

# col1, col2 = st.columns(2)
# with col1:
#     selected_date_1 = st.selectbox("Select a date from Period 1", all_dates_1)
# with col2:
#     selected_date_2 = st.selectbox("Select a date from Period 2", all_dates_2)

# filt_df1 = df1[(df1['timestamp'].dt.date == selected_date_1) & (df1['status'].str.lower() == status_toggle.lower())]
# filt_df2 = df2[(df2['timestamp'].dt.date == selected_date_2) & (df2['status'].str.lower() == status_toggle.lower())]

# if filt_df1.empty or filt_df2.empty:
#     st.info("No matching data for selected dates.")
# else:
#     st.markdown(f"### 📊 Error Comparison: {selected_date_1} vs {selected_date_2}")
#     p1_counts = filt_df1['response_status_code'].value_counts()
#     p2_counts = filt_df2['response_status_code'].value_counts()
#     all_codes = sorted(set(p1_counts.index).union(set(p2_counts.index)))

#     comparison_data = []
#     for code in all_codes:
#         comparison_data.append({
#             "Error Code": code,
#             "Period 1 Count": p1_counts.get(code, 0),
#             "Period 2 Count": p2_counts.get(code, 0)
#         })
#     comparison_df = pd.DataFrame(comparison_data)
#     st.dataframe(comparison_df)

#     for row in comparison_df.itertuples():
#         with st.expander(f"🔎 Error {row._1} Comparison"):
#             col1, col2 = st.columns(2)

#             with col1:
#                 df1_hourly = filt_df1[filt_df1['response_status_code'] == row._1].copy()
#                 df1_hourly['hour'] = df1_hourly['timestamp'].dt.hour
#                 chart1 = px.bar(df1_hourly.groupby('hour').size().reset_index(name='count'), x='hour', y='count',
#                                 title=f"{selected_date_1} Error {row._1}", labels={'hour': 'Hour', 'count': 'Count'})
#                 st.plotly_chart(chart1, use_container_width=True)
#                 if st.button(f"🧠 Analyze {row._1} on {selected_date_1}", key=f"p1_{row._1}"):
#                     with st.spinner("Analyzing..."):
#                         result = analyze_error_hourly_spread(df1_hourly, row._1, selected_date_1, status_toggle)
#                         st.write(result)

#             with col2:
#                 df2_hourly = filt_df2[filt_df2['response_status_code'] == row._1].copy()
#                 df2_hourly['hour'] = df2_hourly['timestamp'].dt.hour
#                 chart2 = px.bar(df2_hourly.groupby('hour').size().reset_index(name='count'), x='hour', y='count',
#                                 title=f"{selected_date_2} Error {row._1}", labels={'hour': 'Hour', 'count': 'Count'})
#                 st.plotly_chart(chart2, use_container_width=True)
#                 if st.button(f"🧠 Analyze {row._1} on {selected_date_2}", key=f"p2_{row._1}"):
#                     with st.spinner("Analyzing..."):
#                         result = analyze_error_hourly_spread(df2_hourly, row._1, selected_date_2, status_toggle)
#                         st.write(result)

# # === END ===



# # # === app.py ===
# # import streamlit as st
# # import pandas as pd
# # from analysis import analyze_graphs, analyze_error_hourly_spread
# # from importdata import load_data_from_csv
# # import plotly.express as px

# # st.set_page_config(layout="wide")
# # st.title("📊 API Telemetry Diagnostics")

# # df = load_data_from_csv("api_telemetry_2_months.xlsx")

# # # Sidebar filters
# # st.sidebar.header("📌 Filter Options")
# # service_options = df['service_name'].dropna().unique().tolist()
# # endpoint_options = df['endpoint'].dropna().unique().tolist()
# # region_options = df['region'].dropna().unique().tolist()

# # selected_services = st.sidebar.multiselect("🛠 Service Name", sorted(service_options))
# # selected_endpoints = st.sidebar.multiselect("📍 Endpoint", sorted(endpoint_options))
# # selected_regions = st.sidebar.multiselect("🌎 Region", sorted(region_options))
# # status_toggle = st.radio("✅ Choose Status to Visualize", ["Success", "Failure"])

# # # Date input for periods
# # st.sidebar.markdown("---")
# # st.sidebar.subheader("🗓️ Period 1")
# # start_date_1 = st.sidebar.date_input("Start Date 1")
# # end_date_1 = st.sidebar.date_input("End Date 1")

# # st.sidebar.subheader("🗓️ Period 2")
# # start_date_2 = st.sidebar.date_input("Start Date 2")
# # end_date_2 = st.sidebar.date_input("End Date 2")

# # start_date_1 = pd.to_datetime(start_date_1).tz_localize("UTC")
# # end_date_1 = pd.to_datetime(end_date_1).tz_localize("UTC") + pd.Timedelta(days=1)
# # start_date_2 = pd.to_datetime(start_date_2).tz_localize("UTC")
# # end_date_2 = pd.to_datetime(end_date_2).tz_localize("UTC") + pd.Timedelta(days=1)

# # if start_date_1 >= end_date_1 or start_date_2 >= end_date_2:
# #     st.error("Start date must be before end date.")
# #     st.stop()

# # # Apply filters
# # if selected_services:
# #     df = df[df['service_name'].isin(selected_services)]
# # if selected_endpoints:
# #     df = df[df['endpoint'].isin(selected_endpoints)]
# # if selected_regions:
# #     df = df[df['region'].isin(selected_regions)]

# # df1 = df[(df['timestamp'] >= start_date_1) & (df['timestamp'] < end_date_1)].copy()
# # df2 = df[(df['timestamp'] >= start_date_2) & (df['timestamp'] < end_date_2)].copy()

# # def plot_counts_by_day(df_filtered, status):
# #     df_filtered = df_filtered[df_filtered['status'].str.lower() == status.lower()]
# #     df_filtered["date"] = df_filtered["timestamp"].dt.date
# #     return df_filtered.groupby("date").size().reset_index(name="count")

# # # Generate charts
# # df1_chart = plot_counts_by_day(df1, status_toggle)
# # df2_chart = plot_counts_by_day(df2, status_toggle)

# # fig1 = px.line(df1_chart, x="date", y="count", title="Period 1", markers=True)
# # fig2 = px.line(df2_chart, x="date", y="count", title="Period 2", markers=True)

# # col1, col2 = st.columns(2)
# # with col1:
# #     st.plotly_chart(fig1, use_container_width=True)
# # with col2:
# #     st.plotly_chart(fig2, use_container_width=True)

# # # GPT Compare (Main LLM Analysis)
# # if st.button("🧠 Analyze with LLM"):
# #     fig1.write_image("temp1.png")
# #     fig2.write_image("temp2.png")
# #     with st.spinner("Analyzing..."):
# #         result = analyze_graphs(
# #             image1_path="temp1.png",
# #             image2_path="temp2.png",
# #             status=status_toggle,
# #             start_date_1=start_date_1,
# #             end_date_1=end_date_1,
# #             start_date_2=start_date_2,
# #             end_date_2=end_date_2,
# #             df1=df1,
# #             df2=df2
# #         )
# #     st.session_state["llm_result"] = result

# # if "llm_result" in st.session_state:
# #     st.markdown("### 🧠 LLM Summary")
# #     st.write(st.session_state["llm_result"])

# # # === 🔍 Per-Day, Per-Error Comparison Drilldown ===
# # st.markdown("## 🔍 Single Day Error Comparison Drilldown")

# # all_dates_1 = sorted(df1['timestamp'].dt.date.unique())
# # all_dates_2 = sorted(df2['timestamp'].dt.date.unique())

# # col1, col2 = st.columns(2)
# # with col1:
# #     selected_date_1 = st.selectbox("Select a date from Period 1", all_dates_1)
# # with col2:
# #     selected_date_2 = st.selectbox("Select a date from Period 2", all_dates_2)

# # filt_df1 = df1[(df1['timestamp'].dt.date == selected_date_1) & (df1['status'].str.lower() == status_toggle.lower())]
# # filt_df2 = df2[(df2['timestamp'].dt.date == selected_date_2) & (df2['status'].str.lower() == status_toggle.lower())]

# # if filt_df1.empty or filt_df2.empty:
# #     st.info("No matching data for selected dates.")
# # else:
# #     st.markdown(f"### 📊 Error Comparison: {selected_date_1} vs {selected_date_2}")
# #     p1_counts = filt_df1['response_status_code'].value_counts()
# #     p2_counts = filt_df2['response_status_code'].value_counts()
# #     all_codes = sorted(set(p1_counts.index).union(set(p2_counts.index)))

# #     comparison_data = []
# #     for code in all_codes:
# #         comparison_data.append({
# #             "Error Code": code,
# #             "Period 1 Count": p1_counts.get(code, 0),
# #             "Period 2 Count": p2_counts.get(code, 0)
# #         })
# #     comparison_df = pd.DataFrame(comparison_data)
# #     st.dataframe(comparison_df)

# #     for row in comparison_df.itertuples():
# #         st.markdown(f"#### 🔎 Error {row._1} Comparison")
# #         col1, col2 = st.columns(2)

# #         with col1:
# #             df1_hourly = filt_df1[filt_df1['response_status_code'] == row._1].copy()
# #             df1_hourly['hour'] = df1_hourly['timestamp'].dt.hour
# #             chart1 = px.bar(df1_hourly.groupby('hour').size().reset_index(name='count'), x='hour', y='count', title=f"{selected_date_1} Error {row._1}")
# #             st.plotly_chart(chart1, use_container_width=True)
# #             if st.button(f"🧠 Analyze {row._1} on {selected_date_1}", key=f"p1_{row._1}"):
# #                 with st.spinner("Analyzing..."):
# #                     result = analyze_error_hourly_spread(df1_hourly, row._1, selected_date_1, status_toggle)
# #                     st.write(result)

# #         with col2:
# #             df2_hourly = filt_df2[filt_df2['response_status_code'] == row._1].copy()
# #             df2_hourly['hour'] = df2_hourly['timestamp'].dt.hour
# #             chart2 = px.bar(df2_hourly.groupby('hour').size().reset_index(name='count'), x='hour', y='count', title=f"{selected_date_2} Error {row._1}")
# #             st.plotly_chart(chart2, use_container_width=True)
# #             if st.button(f"🧠 Analyze {row._1} on {selected_date_2}", key=f"p2_{row._1}"):
# #                 with st.spinner("Analyzing..."):
# #                     result = analyze_error_hourly_spread(df2_hourly, row._1, selected_date_2, status_toggle)
# #                     st.write(result)

# # # === END ===




# # # import streamlit as st
# # # import pandas as pd
# # # from analysis import analyze_graphs, analyze_error_hourly_spread
# # # from importdata import load_data_from_csv
# # # import plotly.express as px

# # # st.set_page_config(layout="wide")
# # # st.title("📊 API Telemetry Diagnostics")

# # # df = load_data_from_csv("api_telemetry_2_months.xlsx")

# # # # Sidebar filters
# # # st.sidebar.header("📌 Filter Options")
# # # service_options = df['service_name'].dropna().unique().tolist()
# # # endpoint_options = df['endpoint'].dropna().unique().tolist()
# # # region_options = df['region'].dropna().unique().tolist()

# # # selected_services = st.sidebar.multiselect("🛠 Service Name", sorted(service_options))
# # # selected_endpoints = st.sidebar.multiselect("📍 Endpoint", sorted(endpoint_options))
# # # selected_regions = st.sidebar.multiselect("🌎 Region", sorted(region_options))
# # # status_toggle = st.radio("✅ Choose Status to Visualize", ["Success", "Failure"])

# # # # Date input for periods
# # # st.sidebar.markdown("---")
# # # st.sidebar.subheader("🗓️ Period 1")
# # # start_date_1 = st.sidebar.date_input("Start Date 1")
# # # end_date_1 = st.sidebar.date_input("End Date 1")

# # # st.sidebar.subheader("🗓️ Period 2")
# # # start_date_2 = st.sidebar.date_input("Start Date 2")
# # # end_date_2 = st.sidebar.date_input("End Date 2")

# # # start_date_1 = pd.to_datetime(start_date_1).tz_localize("UTC")
# # # end_date_1 = pd.to_datetime(end_date_1).tz_localize("UTC") + pd.Timedelta(days=1)
# # # start_date_2 = pd.to_datetime(start_date_2).tz_localize("UTC")
# # # end_date_2 = pd.to_datetime(end_date_2).tz_localize("UTC") + pd.Timedelta(days=1)

# # # if start_date_1 >= end_date_1 or start_date_2 >= end_date_2:
# # #     st.error("Start date must be before end date.")
# # #     st.stop()

# # # # Apply filters
# # # if selected_services:
# # #     df = df[df['service_name'].isin(selected_services)]
# # # if selected_endpoints:
# # #     df = df[df['endpoint'].isin(selected_endpoints)]
# # # if selected_regions:
# # #     df = df[df['region'].isin(selected_regions)]

# # # df1 = df[(df['timestamp'] >= start_date_1) & (df['timestamp'] < end_date_1)].copy()
# # # df2 = df[(df['timestamp'] >= start_date_2) & (df['timestamp'] < end_date_2)].copy()

# # # def plot_counts_by_day(df_filtered, status):
# # #     df_filtered = df_filtered[df_filtered['status'].str.lower() == status.lower()]
# # #     df_filtered["date"] = df_filtered["timestamp"].dt.date
# # #     return df_filtered.groupby("date").size().reset_index(name="count")

# # # # Generate charts
# # # df1_chart = plot_counts_by_day(df1, status_toggle)
# # # df2_chart = plot_counts_by_day(df2, status_toggle)

# # # fig1 = px.line(df1_chart, x="date", y="count", title="Period 1", markers=True)
# # # fig2 = px.line(df2_chart, x="date", y="count", title="Period 2", markers=True)

# # # col1, col2 = st.columns(2)
# # # with col1:
# # #     st.plotly_chart(fig1, use_container_width=True)
# # # with col2:
# # #     st.plotly_chart(fig2, use_container_width=True)

# # # # GPT Compare (Main LLM Analysis)
# # # if st.button("🧠 Analyze with LLM"):
# # #     fig1.write_image("temp1.png")
# # #     fig2.write_image("temp2.png")
# # #     with st.spinner("Analyzing..."):
# # #         result = analyze_graphs(
# # #             image1_path="temp1.png",
# # #             image2_path="temp2.png",
# # #             status=status_toggle,
# # #             start_date_1=start_date_1,
# # #             end_date_1=end_date_1,
# # #             start_date_2=start_date_2,
# # #             end_date_2=end_date_2,
# # #             df1=df1,
# # #             df2=df2
# # #         )
# # #     st.session_state["llm_result"] = result

# # # if "llm_result" in st.session_state:
# # #     st.markdown("### 🧠 LLM Summary")
# # #     st.write(st.session_state["llm_result"])

# # # # === 🔍 Single Day Error Drilldown ===
# # # st.markdown("## 🔍 Single Day Error Drilldown")

# # # available_dates = sorted(df1['timestamp'].dt.date.unique())
# # # selected_date = st.selectbox("Select a date from Period 1", available_dates)

# # # df_day = df1[(df1['timestamp'].dt.date == selected_date) & (df1['status'].str.lower() == status_toggle.lower())]

# # # if df_day.empty:
# # #     st.info("No data found for selected date.")
# # # else:
# # #     error_summary = df_day['response_status_code'].value_counts().reset_index()
# # #     error_summary.columns = ['Error Code', 'Count']
# # #     st.markdown(f"### 📈 Error Summary for {selected_date}")
# # #     st.dataframe(error_summary)

# # #     selected_error = st.selectbox("Select error code to drill down", error_summary['Error Code'])

# # #     df_selected_error = df_day[df_day['response_status_code'] == selected_error].copy()
# # #     df_selected_error['hour'] = df_selected_error['timestamp'].dt.hour
# # #     hourly_counts = df_selected_error.groupby('hour').size().reset_index(name='count')

# # #     fig = px.bar(hourly_counts, x='hour', y='count', title=f"Hourly Distribution of Error {selected_error} on {selected_date}", labels={'hour': 'Hour (0-23)', 'count': 'Count'})
# # #     st.plotly_chart(fig, use_container_width=True)

# # #     if st.button(f"🧠 Analyze Error {selected_error} on {selected_date}"):
# # #         with st.spinner("Analyzing error spread..."):
# # #             result = analyze_error_hourly_spread(
# # #                 df_selected_error,
# # #                 selected_error,
# # #                 selected_date,
# # #                 status_toggle
# # #             )
# # #         st.markdown(f"### 🤖 LLM Observation - Error {selected_error} on {selected_date}")
# # #         st.write(result)