from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import base64
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def compare_images(image1_b64, image2_b64, df1, df2, status, start_date_1, end_date_1, start_date_2, end_date_2):
    # Note: image1_b64 and image2_b64 are base64 PNG images generated from matplotlib plots

    def summarize(df):
        filtered = df[df['status'].str.lower() == status.lower()]
        return filtered.groupby(['service_name', 'endpoint', 'response_status_code']).size().reset_index(name='count').to_string(index=False)

    df1_summary = summarize(df1)
    df2_summary = summarize(df2)

    prompt = f"""
You are an expert in API telemetry diagnostics.

### Visual Input:
- Two charts showing `{status}` trends over two periods (provided as images).

### Tabular Data (grouped by service, endpoint, HTTP code):

#### Period 1 ({start_date_1.date()} → {end_date_1.date()}):
{df1_summary}

#### Period 2 ({start_date_2.date()} → {end_date_2.date()}):
{df2_summary}

### Tasks:
1. Identify dates with large differences (>3%) in `{status}` volume.
2. Analyze possible causes:
- Common errors: 401, 403, 404, 429, 500, 503, 504
- Time-window spikes (e.g., high 500s between 2pm–3pm)
- Differences in endpoint/service behavior
- Throttling or backend/server issues
- Region-specific errors
- High latency or timeouts
3. Analyze the tabular data to suggest **possible reasons**, such as:
    - Missing or invalid parameters in the API request
    - Unauthorized access due to missing or expired tokens (401)
    - Forbidden access when user lacks required permissions (403)
    - Incorrect or unavailable API endpoint requested (404)
    - Too many requests — rate limit exceeded (429)
    - Internal server error (500) — unexpected failure in backend
    - Service unavailable (503) — dependent service is down
    - Gateway timeout (504) due to excessive latency or overload
    - API backend overloaded — too many concurrent requests
    - High latency between request and response (latencyMs, durationMs)
    - Timeout due to long processing or poor connection
    - DNS or connectivity failures on client side
    - Browser incompatibility or CORS issues on specific browsers (browser)
    - Operating system inconsistencies — errors observed only on specific OSes (os)
    - UI problems caused by screen resolution affecting request (screenResolution)
    - Timestamp or clock mismatch affecting sessions (timestamp, sessionId)
    - Failing API operation due to incorrect logic or code bug (operation)
    - Deprecated or invalid API endpoint used (apiEndpoint)
    - Version mismatch between client and server
    - Sudden change in user behavior or traffic pattern (userId, sessionId)
    - Errors are isolated to specific users or sessions (userId, sessionId)
    - Error messages indicating business logic violations (error field)


### Image 1 (base64 PNG):
{image1_b64[:200]}

### Image 2 (base64 PNG):
{image2_b64[:200]}

### Output:
| Period 1 timeline | Period 1 {status} Value |Period 2 timeline | Period 2 {status} Value | Difference | Observation |
- get values for each day from respective graphs provided to you and cross check by calculating total count of {status} value for those days from the dataframe shared to you.
- list all the timelines in markdown
- 3–5 bullet points explaining what might have caused the significant differences.
- Don’t guess — infer only from data shown
- **Use easy understandable technical language** suitable for a developer or operations engineer.
"""

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": "You are a reliable API diagnostics assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500
    )

    return response.choices[0].message.content


def analyze_error_spread(df, error_code, date, status):
    hourly_counts = df.groupby(df['timestamp'].dt.hour).size()
    hourly_str = "\n".join([f"{hour}: {count}" for hour, count in hourly_counts.items()])

    prompt = f"""
You are an expert in API telemetry diagnostics.

### Error Spread Analysis:
- Analyze the hourly distribution of error code {error_code} on {date}.
- Explain what the pattern of occurrence suggests about the cause (e.g., server overload, maintenance, peak usage).
- Use only the data shown, do not speculate beyond it.

### Data Summary (hourly counts):
{hourly_str}

### Output:
- Provide 2-3 bullet points summarizing insights on which time of day is most affected by this error spread and explain why this error spread happened as observed.
"""

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": "You are a reliable API diagnostics assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=800
    )

    return response.choices[0].message.content

# from openai import AzureOpenAI
# from dotenv import load_dotenv
# import os
# import base64
# import logging

# load_dotenv()
# logging.basicConfig(level=logging.INFO)

# client = AzureOpenAI(
#     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
#     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
#     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
# )

# def image_to_base64(path):
#     with open(path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")

# def compare_images(img1_path, img2_path, df1, df2, status, start_date_1, end_date_1, start_date_2, end_date_2):
#     img1_b64 = image_to_base64(img1_path)
#     img2_b64 = image_to_base64(img2_path)

#     def summarize(df):
#         filtered = df[df['status'].str.lower() == status.lower()]
#         return filtered.groupby(['service_name', 'endpoint', 'response_status_code']).size().reset_index(name='count').to_string(index=False)

#     df1_summary = summarize(df1)
#     df2_summary = summarize(df2)

#     prompt = f"""
# You are an expert in API telemetry diagnostics.

# ### Visual Input:
# - Two charts showing `{status}` trends over two periods.

# ### Tabular Data (grouped by service, endpoint, HTTP code):

# #### Period 1 ({start_date_1.date()} → {end_date_1.date()}):
# {df1_summary}

# #### Period 2 ({start_date_2.date()} → {end_date_2.date()}):
# {df2_summary}

# ### Tasks:
# 1. Identify dates with large differences (>3%) in `{status}` volume.
# 2. Analyze possible causes:
# - Common errors: 401, 403, 404, 429, 500, 503, 504
# - Time-window spikes (e.g., high 500s between 2pm–3pm)
# - Differences in endpoint/service behavior
# - Throttling or backend/server issues
# - Region-specific errors
# - High latency or timeouts
# 3. Analyze the tabular data to suggest **possible reasons**, such as:
#     - Missing or invalid parameters in the API request
#     - Unauthorized access due to missing or expired tokens (401)
#     - Forbidden access when user lacks required permissions (403)
#     - Incorrect or unavailable API endpoint requested (404)
#     - Too many requests — rate limit exceeded (429)
#     - Internal server error (500) — unexpected failure in backend
#     - Service unavailable (503) — dependent service is down
#     - Gateway timeout (504) due to excessive latency or overload
#     - API backend overloaded — too many concurrent requests
#     - High latency between request and response (latencyMs, durationMs)
#     - Timeout due to long processing or poor connection
#     - DNS or connectivity failures on client side
#     - Browser incompatibility or CORS issues on specific browsers (browser)
#     - Operating system inconsistencies — errors observed only on specific OSes (os)
#     - UI problems caused by screen resolution affecting request (screenResolution)
#     - Timestamp or clock mismatch affecting sessions (timestamp, sessionId)
#     - Failing API operation due to incorrect logic or code bug (operation)
#     - Deprecated or invalid API endpoint used (apiEndpoint)
#     - Version mismatch between client and server
#     - Sudden change in user behavior or traffic pattern (userId, sessionId)
#     - Errors are isolated to specific users or sessions (userId, sessionId)
#     - Error messages indicating business logic violations (error field)


#   ### Output:
#     | Period 1 timeline | Period 1 {status} Value |Period 2 timeline | Period 2 {status} Value | Difference | Observation |
#     - list all the timelines in markdown
#     - 3–5 bullet points explaining what might have caused the significant differences.
#     - Don’t guess — infer only from data shown
#     - **Use easy understandable technical language** suitable for a developer or operations engineer.

# """

#     response = client.chat.completions.create(
#         model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
#         messages=[
#             {"role": "system", "content": "You are a reliable API diagnostics assistant."},
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": prompt},
#                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_b64}"}},
#                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_b64}"}}
#                 ]
#             }
#         ],
#         max_tokens=1500
#     )

#     return response.choices[0].message.content


# def analyze_error_spread(df, error_code, date, status):
#     # Build hourly counts string for prompt
#     hourly_counts = df.groupby(df['timestamp'].dt.hour).size()
#     hourly_str = "\n".join([f"{hour}: {count}" for hour, count in hourly_counts.items()])

#     prompt = f"""
# You are an expert in API telemetry diagnostics.

# ### Error Spread Analysis:
# - Analyze the hourly distribution of error code {error_code} on {date}.
# - Explain what the pattern of occurrence suggests about the cause (e.g., server overload, maintenance, peak usage).
# - Use only the data shown, do not speculate beyond it.

# ### Data Summary (hourly counts):
# {hourly_str}

# ### Output:
# - Provide 2-3 bullet points summarizing insights on which time of day is most affected by this error spread and explain why this error spread happened as observed.
# """

#     response = client.chat.completions.create(
#         model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
#         messages=[
#             {"role": "system", "content": "You are a reliable API diagnostics assistant."},
#             {"role": "user", "content": prompt}
#         ],
#         max_tokens=800
#     )

#     return response.choices[0].message.content














# # from openai import AzureOpenAI
# # from dotenv import load_dotenv
# # import os
# # import base64
# # import logging

# # load_dotenv()
# # logging.basicConfig(level=logging.INFO)

# # client = AzureOpenAI(
# #     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
# #     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
# #     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
# # )

# # def image_to_base64(path):
# #     with open(path, "rb") as f:
# #         return base64.b64encode(f.read()).decode("utf-8")

# # def compare_images(img1_path, img2_path, df1, df2, status, start_date_1, end_date_1, start_date_2, end_date_2):
# #     img1_b64 = image_to_base64(img1_path) if img1_path else None
# #     img2_b64 = image_to_base64(img2_path) if img2_path else None

# #     def summarize(df):
# #         filtered = df[df['status'].str.lower() == status.lower()]
# #         return filtered.groupby(['service_name', 'endpoint', 'response_status_code']).size().reset_index(name='count').to_string(index=False)

# #     df1_summary = summarize(df1) if df1 is not None else ""
# #     df2_summary = summarize(df2) if df2 is not None else ""

# #     prompt = f"""
# # You are an expert in API telemetry diagnostics.

# # ### Visual Input:
# # - Two charts showing `{status}` trends over two periods.

# # ### Tabular Data (grouped by service, endpoint, HTTP code):

# # #### Period 1 ({start_date_1.date() if start_date_1 else 'N/A'} → {end_date_1.date() if end_date_1 else 'N/A'}):
# # {df1_summary}

# # #### Period 2 ({start_date_2.date() if start_date_2 else 'N/A'} → {end_date_2.date() if end_date_2 else 'N/A'}):
# # {df2_summary}

# # ### Tasks:
# # 1. Identify dates with large differences (>3%) in `{status}` volume.
# # 2. Analyze possible causes:
# # - Common errors: 401, 403, 404, 429, 500, 503, 504
# # - Time-window spikes (e.g., high 500s between 2pm–3pm)
# # - Differences in endpoint/service behavior
# # - Throttling or backend/server issues
# # - Region-specific errors
# # - High latency or timeouts


# # ### Output format:
# # - Table showing key differences (date-wise)
# # - 3–5 bullet insights
# # - Don’t guess — infer only from data shown
# # """

# #     messages = [
# #         {"role": "system", "content": "You are a reliable API diagnostics assistant."},
# #         {
# #             "role": "user",
# #             "content": [
# #                 {"type": "text", "text": prompt}
# #             ]
# #         }
# #     ]

# #     if img1_b64:
# #         messages[-1]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_b64}"}})
# #     if img2_b64:
# #         messages[-1]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_b64}"}})

# #     response = client.chat.completions.create(
# #         model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
# #         messages=messages,
# #         max_tokens=1500
# #     )

# #     return response.choices[0].message.content










# # # from openai import AzureOpenAI
# # # from dotenv import load_dotenv
# # # import os
# # # import base64
# # # import logging

# # # load_dotenv()
# # # logging.basicConfig(level=logging.INFO)

# # # client = AzureOpenAI(
# # #     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
# # #     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
# # #     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
# # # )

# # # def compare_images(img1_path, img2_path, df1, df2, status, start_date_1, end_date_1, start_date_2, end_date_2):
# # #     def image_to_base64_optional(path):
# # #         if path is None:
# # #             return None
# # #         with open(path, "rb") as f:
# # #             return base64.b64encode(f.read()).decode("utf-8")

# # #     img1_b64 = image_to_base64_optional(img1_path)
# # #     img2_b64 = image_to_base64_optional(img2_path)

# # #     def summarize(df):
# # #         filtered = df[df['status'].str.lower() == status.lower()]
# # #         filtered['date'] = filtered['timestamp'].dt.date
# # #         return filtered.groupby(['date']).size().reset_index(name='count').to_string(index=False)

# # #     df1_summary = summarize(df1)
# # #     df2_summary = summarize(df2)

# # #     prompt = f"""
# # # You are an expert in API telemetry diagnostics.

# # # ### Task: Compare Period 1 and Period 2 using below grouped status data.

# # # ### Data (status = {status}):

# # # #### Period 1 ({start_date_1.date() if start_date_1 else "N/A"}):
# # # {df1_summary}

# # # #### Period 2 ({start_date_2.date() if start_date_2 else "N/A"}):
# # # {df2_summary}

# # # ### Output Format:
# # # Provide a markdown table like this:

# # # | Period 1 Date | Period 1 {status} Count | Period 2 Date | Period 2 {status} Count | Change (%) | Observation (>10%) |
# # # |----------------|--------------------------|----------------|--------------------------|------------|---------------------|
# # # |                |                          |                |                          |            |                     |
# # # fill the table with dates where there are significant differences in `{status}` counts between the two periods.
# # # Also provide 3–5 key bullet point insights.
# # # ### Analysis Instructions:
# # # Analyze the data for significant differences in `{status}` counts between the two periods.

# # # Check for:
# # # - Top error codes (e.g., 403, 404, 500, etc.)
# # # - Any hourly spikes or dips
# # # - Latency or throttling effects
# # # - Backend or region anomalies
# # # """

# # #     content = [{"type": "text", "text": prompt}]
# # #     if img1_b64:
# # #         content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_b64}"}})
# # #     if img2_b64:
# # #         content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_b64}"}})

# # #     response = client.chat.completions.create(
# # #         model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
# # #         messages=[
# # #             {"role": "system", "content": "You are a reliable API diagnostics assistant."},
# # #             {"role": "user", "content": content}
# # #         ],
# # #         max_tokens=1500
# # #     )

# # #     return response.choices[0].message.content








# # # # from openai import AzureOpenAI
# # # # from dotenv import load_dotenv
# # # # import os
# # # # import base64
# # # # import logging

# # # # load_dotenv()
# # # # logging.basicConfig(level=logging.INFO)

# # # # client = AzureOpenAI(
# # # #     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
# # # #     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
# # # #     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
# # # # )

# # # # def image_to_base64(path):
# # # #     with open(path, "rb") as f:
# # # #         return base64.b64encode(f.read()).decode("utf-8")

# # # # def compare_images(img1_path, img2_path, df1, df2, status, start_date_1, end_date_1, start_date_2, end_date_2):
# # # #     img1_b64 = image_to_base64(img1_path)
# # # #     img2_b64 = image_to_base64(img2_path)

# # # #     def summarize(df):
# # # #         filtered = df[df['status'].str.lower() == status.lower()]
# # # #         return filtered.groupby(['service_name', 'endpoint', 'response_status_code']).size().reset_index(name='count').to_string(index=False)

# # # #     df1_summary = summarize(df1)
# # # #     df2_summary = summarize(df2)

# # # #     prompt = f"""
# # # # You are an expert in API telemetry diagnostics.

# # # # ### Visual Input:
# # # # - Two charts showing `{status}` trends over two periods.

# # # # ### Tabular Data (grouped by service, endpoint, HTTP code):

# # # # #### Period 1 ({start_date_1.date()} → {end_date_1.date()}):
# # # # {df1_summary}

# # # # #### Period 2 ({start_date_2.date()} → {end_date_2.date()}):
# # # # {df2_summary}

# # # # ### Tasks:
# # # # 1. Identify dates with large differences (>3%) in `{status}` volume.
# # # # 2. Analyze possible causes:
# # # # - Common errors: 401, 403, 404, 429, 500, 503, 504
# # # # - Time-window spikes (e.g., high 500s between 2pm–3pm)
# # # # - Differences in endpoint/service behavior
# # # # - Throttling or backend/server issues
# # # # - Region-specific errors
# # # # - High latency or timeouts

# # # # ### Output format:
# # # # - Table showing key differences (date-wise)
# # # # - 3–5 bullet insights
# # # # - Don’t guess — infer only from data shown
# # # # """

# # # #     response = client.chat.completions.create(
# # # #         model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
# # # #         messages=[
# # # #             {"role": "system", "content": "You are a reliable API diagnostics assistant."},
# # # #             {
# # # #                 "role": "user",
# # # #                 "content": [
# # # #                     {"type": "text", "text": prompt},
# # # #                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_b64}"}},
# # # #                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_b64}"}}
# # # #                 ]
# # # #             }
# # # #         ],
# # # #         max_tokens=1500
# # # #     )

# # # #     return response.choices[0].message.content
