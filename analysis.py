from openai_client import compare_images, analyze_error_spread

def analyze_graphs(image1_path, image2_path, status, start_date_1=None, end_date_1=None, start_date_2=None, end_date_2=None, df1=None, df2=None):
    try:
        summary = compare_images(
            image1_path,
            image2_path,
            df1=df1,
            df2=df2,
            status=status,
            start_date_1=start_date_1,
            end_date_1=end_date_1,
            start_date_2=start_date_2,
            end_date_2=end_date_2
        )
        return summary
    except Exception as e:
        return f"Error: {e}"

def analyze_error_hourly_spread(df, error_code, date, status):
    try:
        return analyze_error_spread(df, error_code, date, status)
    except Exception as e:
        return f"Error: {e}"





# from openai_client import compare_images

# def analyze_graphs(image1_path, image2_path, status, start_date_1=None, end_date_1=None, start_date_2=None, end_date_2=None, df1=None, df2=None):
#     try:
#         summary = compare_images(
#             image1_path,
#             image2_path,
#             df1=df1,
#             df2=df2,
#             status=status,
#             start_date_1=start_date_1,
#             end_date_1=end_date_1,
#             start_date_2=start_date_2,
#             end_date_2=end_date_2
#         )
#         return summary
#     except Exception as e:
#         return f"Error: {e}"
