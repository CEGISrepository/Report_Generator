import os
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import pandas as pd
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import base64
import secrets
from xhtml2pdf import pisa
from twilio.rest import Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import matplotlib as mpl
from urllib.parse import quote
import requests
import pdfkit
import zipfile
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import datetime
import json
from jinja2 import Environment, FileSystemLoader
import time
import matplotlib
matplotlib.use('Agg')

reports_base_folder = os.path.join(os.getcwd(), 'phone_survey_reports')

# Create a timestamped subfolder for each run
timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
report_folder = os.path.join(reports_base_folder, f'report_{timestamp}')
os.makedirs(report_folder, exist_ok=True)


mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial']

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)  # Generate a secure secret key
app.static_folder = 'static'  # Set the static folder

# Twilio configuration
account_sid = ' '
auth_token = ' '
twilio_phone_number = '+ '
client = Client(account_sid, auth_token)


# Google Drive API configuration
creds = Credentials.from_authorized_user_file('credentials.json', ['https://www.googleapis.com/auth/drive'])
drive_service = build ('drive', 'v3', credentials=creds)


mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial']


PARENT_FOLDER_ID = '1Z2D8r9ryOpeFkmUzC1Ur1FpNtvDVq9_8'


def generate_chart(df, x_column, y_column, chart_type, chart_title, x_label, y_label, filename, threshold, chart_color,
                   analysis_level, area):
    """
        Generates a chart (bar, line, pie, or scatter) based on the given data and configuration.

        Args:
            df (pandas.DataFrame): The DataFrame containing the data to plot.
            x_column (str): The column name to use for the x-axis.
            y_column (str): The column name to use for the y-axis.
            chart_type (str): The type of chart ('bar', 'line', 'pie', or 'scatter').
            chart_title (str): The title of the chart.
            x_label (str): The label for the x-axis.
            y_label (str): The label for the y-axis.
            filename (str): The filename to save the chart image.
            threshold (float or None): Optional threshold value for horizontal line.
            chart_color (str or list): Color(s) for the chart elements.
            analysis_level (str): The level of analysis ('District' or 'SubDistrict').
            area (str): The specific district or sub-district to filter by.


        Returns:
            tuple: A tuple containing the chart file path and the base64 encoded image data.
        """
    # Sanitize input variables to create safe filenames for the chart images.
    # This ensures that the filenames don't contain invalid characters that could cause issues on the file system or in other parts of the code.
    # This is particularly important if the input variables are coming from user-provided data,
    # as this could be a potential security risk

    if isinstance(area, str):
        safe_area = "".join(c for c in area if c.isalnum() or c in "_- .")
    else:
        safe_area = ""
    safe_x_column = "".join(c for c in str(x_column) if c.isalnum() or c in "_- .")
    safe_y_column = "".join(c for c in str(y_column) if c.isalnum() or c in "_- .")
    safe_chart_type = "".join(c for c in str(chart_type) if c.isalnum() or c in "_- .")

    print(f"Generating chart for area: {safe_area}, x_column: {safe_x_column}, y_column: {safe_y_column}, chart_type: {safe_chart_type}")

    # Filter the data for the specific area
    area_df = df[df[analysis_level] == area].copy()

    # Check if any data available
    if area_df.empty:
        print(f"No data available for {area} - {x_column} vs {y_column}")
        return None  # Return None if no data

    # Aggregate data for bar, line, and pie charts
    if chart_type in ['bar', 'line', 'pie']:
        # Group by the x_column (categorical) and sum y_column values if numeric
        if pd.api.types.is_numeric_dtype(area_df[y_column]):
            plot_data = area_df.groupby(x_column)[y_column].sum()

            # Sort the plot data for bar charts (optional)
            if chart_type == 'bar':
                plot_data = plot_data.sort_values()

        else:
            print(f"y_column ({y_column}) is not numeric for {chart_type} chart in {area}.")
            return None

    elif chart_type == 'scatter':
        # No aggregation needed for scatter plots
        plot_data = area_df[[x_column, y_column]]

        # Check and convert columns to numeric (for scatter plots)
        for col in [x_column, y_column]:
            if not pd.api.types.is_numeric_dtype(area_df[col]):
                print(f"Non-numeric values found in column {col} for {area}. Converting to numeric if possible.")
                area_df[col] = pd.to_numeric(area_df[col], errors='coerce')

    else:
        # Handle other chart types or invalid input (e.g., raise an exception)
        print(f"Invalid chart type: {chart_type}")
        return None

    # Remove rows with missing values after conversion
    area_df.dropna(subset=[x_column, y_column], inplace=True)

    if area_df.empty:
        print(f"No valid numeric data for {area} - {x_column} vs {y_column}")
        return None

    # Generate plot
    plt.figure(figsize=(1.5, 1))
    ax = plt.gca()
    ax.set_facecolor('white')

    try:
        if chart_type == 'pie':
            wedges, texts, autotexts = ax.pie(plot_data.values, labels=plot_data.index, autopct='%1.1f%%',
                                              startangle=90,
                                              textprops={'fontsize': 3})
            plt.setp(autotexts, size=2, weight='bold')
            ax.axis('equal')  # Equal aspect ratio ensures that the pie chart is drawn as a circle
            plt.legend(wedges, plot_data.index, loc='center left', bbox_to_anchor=(1.0, 0.5), fontsize=4)
        elif chart_type == 'scatter':
            ax.scatter(plot_data[x_column], plot_data[y_column], color=chart_color)
        else:
            plot = plot_data.plot(kind=chart_type, ax=ax, color=chart_color)

        # Add horizontal line for threshold
        if threshold is not None and isinstance(threshold, (int, float)):
            threshold_value = float(threshold)
            ax.axhline(y=threshold_value, color='r', linewidth=0.5, linestyle='--',
                       label=f'Threshold: {threshold_value}')
            ax.legend(loc='upper right', fontsize=2.5)

        ax.set_title(chart_title, fontsize=4)
        ax.set_xlabel(x_label, fontsize=3)
        ax.set_ylabel(y_label, fontsize=3)
        plt.xticks(fontsize=2.5)
        plt.yticks(fontsize=2.5)

        safe_filename = "".join(c for c in filename if c.isalnum() or c in "_- .")
        charts_folder = os.path.join(report_folder, 'charts')
        os.makedirs(charts_folder, exist_ok=True)

        chart_path = os.path.join(report_folder, 'charts', safe_filename)
        plt.savefig(chart_path, bbox_inches='tight', dpi=300)

        # Read the chart image file and encode it as a base64 string. This will be used to render the preview template for the report.
        with open(chart_path, 'rb') as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            print(f"Encoded image data length: {len(encoded_image)}")

        plt.close()

        return chart_path, encoded_image
    except Exception as e:  # Add the except clause here
        print(f"Error generating chart: {e}")
        # Consider returning None or a default image here
        return None

@app.route('/')
def instructions():
    """
    This is the homepage of the website where instructions for the use
    of the website are displayed. Users need to click on proceed to move to the actual portal.
    """
    instructions_points = [
        "The dataset is assumed to be well known by the user. That is, the user is aware of what the contents and columns of the dataset imply.",
        "The dataset is already cleaned, if needed, by the user.",
        "There must be no coded categorical variables in the dataset and if not so, they must converted to the text value that they imply. For example, if there are coded values like 0 and 1 where 0 implies 'Didn't pick up phone' and 1 implies 'Picked up by expected receiver', then 0 and 1 should be replaced with their values themselves.",
        "The data file and phone numbers files must be in .csv format as shown in the template provided. ",
        "After entering input details, it is advisable to save the input as a pre-set by giving it a name. This can be loaded back in-case of loss of the input information.",
        "Appropriate data types must be input for the desired plot. For example, pie plots can't be composed of only numeric data. ",
        "Detailed instructions available at : https://github.com/CEGISrepository/Report_Generator/tree/main"
    ]
    return render_template('instructions.html', instructions_points=instructions_points)

@app.route('/index')
# Renders the index.html template, which serves as the main interface of our web application
def index():
    return render_template('index.html')

def shorten_url(url):
    #Using the Bitly URL shortener (sign up for an account and get an access token)
    bitly_access_token = 'YOUR_BITLY_ACCESS_TOKEN'
    bitly_api_url = 'https://api-ssl.bitly.com/v4/shorten'
    headers = {
        'Authorization': f'Bearer {bitly_access_token}',
        'Content-Type': 'application/json'
    }
    data = {'long_url': url}

    response = requests.post(bitly_api_url, headers=headers, json=data)
    if response.status_code == 200:
        shortened_url = response.json()['link']
        return shortened_url
    else:
        # Handle error cases
        print(f"Error shortening URL: {response.status_code} - {response.text}")
        return url
def send_sms(phone_numbers, file_url):
    # Send the download link as an SMS to the provided phone numbers
    for phone_number in phone_numbers:
        # Convert phone_number to string
        phone_number = str(phone_number)

        # Preprocess the phone number if needed
        if not phone_number.startswith('+'):
            phone_number = '+91' + phone_number  # Assuming Indian phone numbers

        # Shorten the download link using a URL shortener service
        shortened_url = shorten_url(file_url)

        message = client.messages.create(
            body=f"Download your report PDF: {shortened_url}",
            from_=twilio_phone_number,
            to=phone_number
        )
        print(f"SMS sent to {phone_number}")



@app.route('/analyze', methods=['POST'])
def analyze():
    """
          This function handles the main analysis and report generation workflow:

            1. Retrieves uploaded files (data file and phone numbers file).
            2. Reads and processes the CSV data.
            3. Collects user-specified chart configurations and filters.
            4. Creates a timestamped folder on Google Drive for storing reports.
            5. Iterates over each analysis area (district/sub-district) in the data.
            6. Filters the data for each area based on user-defined filters.
            7. Generates charts using the `generate_chart` function.
            8. Calculates statistics (min, max, avg, mode, median) for each chart.
            9. Generates PDF reports using the `create_pdf` function.
            10. Uploads generated reports (charts and PDFs) to Google Drive.
            11. Optionally sends SMS notifications with links to the reports.
            12. Renders the appropriate response:
                * Error message if files are missing.
                * Preview of the first report in a modal if 'preview' action is selected.
                * Flash message indicating successful report generation if 'save' action is selected.
                * Flash message indicating SMS sent if 'send_sms' action is selected.

            Returns:
                Flask response: Either an error message, the preview page, or the index page with a flash message.
            """
    data_file = request.files.get('data_file')
    phone_numbers_file = request.files.get('phone_numbers_file')
    analysis_level = request.form.get('analysis_level')
    report_title = request.form.get('report_title', 'Default Report Title')

    # Check if both files are uploaded
    if data_file and phone_numbers_file:
        # Read data from CSV files
        data_csv = data_file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(data_csv))

        phone_numbers_csv = phone_numbers_file.read().decode('utf-8')
        phone_numbers_df = pd.read_csv(io.StringIO(phone_numbers_csv))

        # Extract column names and unique areas based on analysis level
        column_names = df.columns.tolist()
        areas = df[analysis_level].unique()

        # Get the requested action (preview, save, or send_sms)
        action = request.form.get('action')
        chart_configs = []

        # Iterate over each chart configuration in the form data
        num_charts = int(request.form.get('num_charts', 0))
        for i in range(num_charts):
            # Collect chart configuration
            x_column = request.form.get(f'x_column_{i + 1}')
            y_column = request.form.get(f'y_column_{i + 1}')
            chart_type = request.form.get(f'chart_type_{i + 1}')
            chart_title = request.form.get(f'chart_title_{i + 1}')
            x_label = request.form.get(f'x_label_{i + 1}', '')
            y_label = request.form.get(f'y_label_{i + 1}', '')
            description = request.form.get(f'description_{i + 1}', '')
            threshold_str = request.form.get(f'threshold_{i + 1}', '')
            threshold = float(threshold_str) if threshold_str.strip() else None
            chart_color = request.form.get(f'chart_color_{i + 1}', '#61a673')

            # Collect filters
            filters = []
            filter_count = 1
            while f'filter_action_{i}_{filter_count}' in request.form:
                filter_action = request.form.get(f'filter_action_{i}_{filter_count}')
                filter_column = request.form.get(f'filter_column_{i}_{filter_count}')
                filter_type = request.form.get(f'filter_type_{i}_{filter_count}')
                if filter_type == 'range':
                    min_val = request.form.get(f'filter_min_{i}_{filter_count}', None)
                    max_val = request.form.get(f'filter_max_{i}_{filter_count}', None)
                    filters.append({
                        'action': filter_action,
                        'column': filter_column,
                        'type': filter_type,
                        'min': float(min_val) if min_val else None,
                        'max': float(max_val) if max_val else None
                    })
                elif filter_type == 'text':
                    text_val = request.form.get(f'filter_text_{i}_{filter_count}', '')
                    filters.append({
                        'action': filter_action,
                        'column': filter_column,
                        'type': filter_type,
                        'text': text_val
                    })
                filter_count += 1

            chart_configs.append({
                'x_column': x_column,
                'y_column': y_column,
                'chart_type': chart_type,
                'chart_title': chart_title,
                'x_label': x_label,
                'y_label': y_label,
                'description': description,
                'threshold': threshold,
                'chart_color': chart_color,
                'filters': filters
            })

        # Get report text from form data
        report_text = request.form.get('report_text', '')

        # Create Google Drive service
        service = build('drive', 'v3', credentials=creds)

        # Create a timestamped folder in Google Drive under 'phone_survey_reports'
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        drive_folder_name = f'report_{timestamp}'
        parent_folder_id = PARENT_FOLDER_ID  # Ensure this is set to the ID of 'phone_survey_reports' folder
        report_folder_id = create_drive_folder(service, drive_folder_name, parent_folder_id)

        if not report_folder_id:
            flash('Failed to create a new folder in Google Drive.')
            return render_template('index.html', column_names=column_names)

        district_report_links = {}

        # Iterate over each area and generate reports
        for area in areas:
            area_df = df[df[analysis_level] == area]
            if area_df.empty:
                print(f"No data for {area}")
                continue

            chart_infos = []

            for config in chart_configs:
                filtered_data = area_df.copy()

                # Apply filters
                for f in config['filters']:
                    if f['type'] == 'range':
                        if f['min'] is not None:
                            if f['action'] == 'keep':
                                filtered_data = filtered_data[filtered_data[f['column']] >= f['min']]
                            else:
                                filtered_data = filtered_data[filtered_data[f['column']] < f['min']]
                        if f['max'] is not None:
                            if f['action'] == 'keep':
                                filtered_data = filtered_data[filtered_data[f['column']] <= f['max']]
                            else:
                                filtered_data = filtered_data[filtered_data[f['column']] > f['max']]
                    elif f['type'] == 'text':
                        if f['action'] == 'keep':
                            filtered_data = filtered_data[
                                filtered_data[f['column']].astype(str).str.contains(f['text'], na=False)]
                        else:
                            filtered_data = filtered_data[
                                ~filtered_data[f['column']].astype(str).str.contains(f['text'], na=False)]

                if filtered_data.empty:
                    print(f"No data after filtering for {area} - {config['x_column']} vs {config['y_column']}")
                    continue

                filename = f"{area}_{config['x_column']}_{config['y_column']}_{analysis_level}.png"
                chart_path, encoded_image = generate_chart(
                    filtered_data,
                    config['x_column'],
                    config['y_column'],
                    config['chart_type'],
                    config['chart_title'],
                    config['x_label'],
                    config['y_label'],
                    filename,
                    config['threshold'],
                    config['chart_color'],
                    analysis_level,
                    area
                )


                if chart_path is None:
                    print("Chart path is None")
                else:
                    print(f"Chart path: {chart_path}")

                if encoded_image is None:
                    print("Encoded image is None")
                else:
                    print(f"Encoded image length: {len(encoded_image)}")

                print(f"Encoded image data: {encoded_image[:20]}...")
                # Upload chart to Google Drive
                file_id = upload_file_to_drive(service, chart_path, report_folder_id, filename, analysis_level)

                x_column = config['x_column']
                y_column = config['y_column']
                chart_type = config['chart_type']
                chart_title = config['chart_title']
                x_label = config['x_label']
                y_label = config['y_label']
                description = config['description']
                threshold = config['threshold']
                chart_color = config['chart_color']
                filename = f"{area}_{x_column}_{y_column}_{analysis_level}.png"

                y_column_data = filtered_data[y_column]
                min_value = y_column_data.min()
                max_value = y_column_data.max()
                avg_value = y_column_data.mean()
                mode_value = y_column_data.mode().iloc[0]
                median_value = y_column_data.median()

                chart_infos.append({
                    'filename': filename,
                    'chart_title': chart_title,
                    'x_label': x_label,
                    'y_label': y_label,
                    'description': description,
                    'min_' + y_column: min_value,
                    'max_' + y_column: max_value,
                    'avg_' + y_column: avg_value,
                    'mode_' + y_column: mode_value,
                    'median_' + y_column: median_value,
                    'y_column': y_column,
                    'file_id': file_id,
                    'chart_path': chart_path  # Add the base64 string to the dictionary
                })

            pdf_filename = f"{area}_{analysis_level}_report.pdf"
            pdf_file_id = create_pdf(pdf_filename, area, chart_infos, report_text, service, report_folder_id, analysis_level, report_folder, report_title=report_title)

            # Upload PDF to Google Drive
            if pdf_file_id:
                file_url = f"https://drive.google.com/file/d/{pdf_file_id}/view?usp=sharing"
                district_report_links[area] = file_url

            if action == 'save':
                flash(f'Saved {pdf_filename} to Google Drive.')

        if action == 'send_sms':
            # Send SMS messages with links to report PDFs
            for area in phone_numbers_df[analysis_level].unique():
                area_phone_numbers = phone_numbers_df[phone_numbers_df[analysis_level] == area]['phone_no']
                if area in district_report_links:
                    file_url = district_report_links[area]
                    print(file_url)
                    # Optionally send an SMS message with the report URL for the current area
                    send_sms(area_phone_numbers, file_url)
                    flash(f'Sent SMS with link to {area}_{analysis_level}_report.pdf.')
        if action == 'preview':
            # Generate and display a preview of the report for the first area
            if len(areas) > 0:
                first_area = areas[0]
                chart_infos = []     # Reset chart_infos for the preview

                # Iterate over each chart configuration and generate chart images
                for config in chart_configs:
                    filtered_data = df[df[analysis_level] == first_area].copy()

                    # Apply filters
                    for f in config['filters']:
                        if f['type'] == 'range':
                            if f['min'] is not None:
                                filtered_data = filtered_data[filtered_data[f['column']] >= f['min']] if f[
                                                                                                             'action'] == 'keep' else \
                                filtered_data[filtered_data[f['column']] < f['min']]
                            if f['max'] is not None:
                                filtered_data = filtered_data[filtered_data[f['column']] <= f['max']] if f[
                                                                                                             'action'] == 'keep' else \
                                filtered_data[filtered_data[f['column']] > f['max']]
                        elif f['type'] == 'text':
                            filtered_data = filtered_data[
                                filtered_data[f['column']].astype(str).str.contains(f['text'], na=False)] if f[
                                                                                                                 'action'] == 'keep' else \
                            filtered_data[~filtered_data[f['column']].astype(str).str.contains(f['text'], na=False)]

                    # If no data remains after filtering, skip this chart
                    if filtered_data.empty:
                        continue  # Skip if no data after filtering

                    # Generate chart (modified for preview)
                    filename = f"{first_area}_{config['x_column']}_{config['y_column']}_{analysis_level}.png"

                    # Create a new dictionary with only the required arguments for generate_chart
                    chart_config_for_generate_chart = {key: config[key] for key in config if
                                                       key in ['x_column', 'y_column', 'chart_type', 'chart_title',
                                                               'x_label', 'y_label', 'threshold', 'chart_color']}
                    chart_path, encoded_image = generate_chart(filtered_data, filename=filename,
                                                               analysis_level=analysis_level, area=first_area,
                                                               **chart_config_for_generate_chart)

                    # Check if the chart image was successfully generated
                    if encoded_image:
                        # Create a Data URL (data URI) for the chart image
                        # This is a special format that allows embedding the base64-encoded image data directly into the HTML content
                        chart_data = f"data:image/png;base64,{encoded_image}"

                        # Extract data from the filtered DataFrame for the y-column
                        y_column_data = filtered_data[config['y_column']]
                        # Append the chart information dictionary to the list of chart infos
                        chart_infos.append({
                            'filename': filename,
                            'chart_title': config['chart_title'],
                            'x_label': config['x_label'],
                            'y_label': config['y_label'],
                            'description': config.get('description', ''),
                            'min_' + config['y_column']: y_column_data.min(),
                            'max_' + config['y_column']: y_column_data.max(),
                            'avg_' + config['y_column']: y_column_data.mean(),
                            'mode_' + config['y_column']: y_column_data.mode().iloc[0],
                            'median_' + config['y_column']: y_column_data.median(),
                            'y_column': config['y_column'],
                            'chart_data': chart_data
                        })

                # Render the preview
                preview_html = render_template('preview_template.html', district=first_area, chart_infos=chart_infos,
                                               report_text=report_text, report_title=report_title)
                return render_template('preview.html', preview_html=preview_html, column_names=column_names)

            else:
                flash('No report available for preview.')
                return render_template('index.html', column_names=column_names)

        return render_template('index.html', column_names=column_names)
    else:
        return 'Files missing'

@app.route('/save_preset', methods=['POST'])
def save_preset():
    """
        This function handles the saving of chart presets:

        1. Retrieves the preset name from the form data.
        2. Validates that a preset name has been provided.
        3. Collects all relevant chart configuration data from the form, excluding the preset name itself.
        4. Loads existing presets from the 'presets.json' file (or initializes an empty dictionary if the file doesn't exist).
        5. Adds the new preset data to the dictionary of existing presets.
        6. Saves the updated presets back to the 'presets.json' file, maintaining indentation for readability.
        7. Returns a JSON response indicating the success or failure of the operation.

        Returns:
            Flask Response: A JSON object with the following keys:
                * 'status': 'success' if the preset was saved successfully, 'error' otherwise.
                * 'message': An optional message providing additional details about the outcome (e.g., an error message).
        """
    # Get the preset name from the form data
    preset_name = request.form.get('preset_name')
    # Validate that a preset name was provided
    if not preset_name:
        return jsonify({'status': 'error', 'message': 'No preset name provided'})

    # Collect all relevant chart configuration data from the form, excluding the preset name
    preset_data = {key: value for key, value in request.form.items() if key != 'preset_name'}

    try:
        # Try to load existing presets from the 'presets.json' file
        with open('presets.json', 'r') as f:
            presets = json.load(f)
    # If the file doesn't exist or has invalid JSON, start with an empty dictionary
    except (FileNotFoundError, json.JSONDecodeError):
        presets = {}

    presets[preset_name] = preset_data

    with open('presets.json', 'w') as f:
        json.dump(presets, f, indent=4)

    # Return a success JSON response
    return jsonify({'status': 'success'})

@app.route('/load_preset/<preset_name>')
def load_preset(preset_name):
    """
        This function handles the loading of saved chart presets:

        1. Retrieves the requested preset name from the URL parameter.
        2. Attempts to load all saved presets from the 'presets.json' file.
        3. If the requested preset name is found in the loaded presets:
            * Returns the preset data as a JSON response with status 'success'.
        4. If the file doesn't exist or has invalid JSON, returns an error JSON response.
        5. If the requested preset name is not found, returns an error JSON response.

        Args:
            preset_name (str): The name of the preset to load.

        Returns:
            Flask Response: A JSON object with the following keys:
                * 'status': 'success' if the preset was loaded successfully, 'error' otherwise.
                * 'preset': The preset data (a dictionary) if loaded successfully, otherwise None.
                * 'message': An optional message providing additional details about the outcome (e.g., an error message).
        """
    # Try to load existing presets from the 'presets.json' file
    try:
        with open('presets.json', 'r') as f:
            presets = json.load(f)
    # If the file doesn't exist or has invalid JSON, return an error JSON response
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'status': 'error', 'message': 'No presets found'})

    # If the requested preset name is not found, return an error JSON response
    if preset_name not in presets:
        return jsonify({'status': 'error', 'message': 'Preset not found'})

    # Return the preset data as a JSON response with status 'success'
    return jsonify({'status': 'success', 'preset': presets[preset_name]})

@app.route('/get_presets')
def get_presets():
    """
        This function retrieves the list of saved chart presets from the 'presets.json' file and returns them as a JSON response.

        1. Attempts to open and read the contents of the 'presets.json' file.
        2. If the file exists and contains valid JSON data, it extracts the preset names (keys of the JSON object) and returns them in a list.
        3. If the 'presets.json' file does not exist, it returns an empty list, indicating that there are no saved presets.
        4. If the file exists but contains invalid JSON data, it logs the error and returns an empty list along with an error message.

        Returns:
            Flask Response: A JSON object with the following keys:
                * 'presets': A list of strings representing the names of saved presets, or an empty list if there are no presets or an error occurred.
                * 'error': An optional string containing an error message if there was an issue reading the presets file.
        """

    try:
        # Attempt to open and read the contents of the 'presets.json' file in read mode ('r')
        with open('presets.json', 'r') as f:
            # Parse the JSON data from the file and load it into a dictionary called 'presets'
            presets = json.load(f)
    # Handle the case where the 'presets.json' file is not found (FileNotFoundError)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading presets.json: {e}")
        # Return a JSON response indicating no presets were found and include the error message
        return jsonify({'presets': [], 'error': str(e)}), 500

    try:
        preset_names = list(presets.keys())
        return jsonify({'presets': preset_names})
    # Handle other exceptions that might occur while reading the JSON file (e.g., invalid JSON syntax)
    except Exception as e:
        print(f"Error getting preset names: {e}")   # Log the error for debugging
        # Return a JSON response indicating no presets were found and include the error message
        return jsonify({'presets': [], 'error': str(e)}), 500


def create_pdf(pdf_filename, area, chart_infos, report_text, service, report_folder_id, analysis_level,
               report_folder=None, report_title='Default Report Title'):
    modified_chart_infos = []
    """
        This function creates a PDF report for a specific area (district or sub-district).

        Steps:
        1. Prepares chart data by embedding images either directly from base64 encoded data (if available from preview) or
           by fetching the images from Google Drive and encoding them.
        2. Renders the PDF template ('pdf_template.html') using Jinja2, passing the chart data, report text, report title,
           and other relevant information.
        3. Creates a BytesIO object to hold the PDF data in memory.
        4. Uses xhtml2pdf's pisa.CreatePDF to convert the rendered HTML into a PDF, utilizing the `link_callback` function
           to resolve relative paths to images and other resources.
        5. If PDF creation is successful:
           * Prepares file metadata for uploading to Google Drive.
           * Creates a MediaIoBaseUpload object to handle the PDF data.
           * Uploads the PDF to Google Drive using the provided service object and folder ID.
           * Returns the ID of the uploaded PDF file.
        6. If PDF creation fails:
           * Prints an error message.
           * Returns None.

        Args:
            pdf_filename (str): Name of the PDF file to be created.
            area (str): The name of the district or sub-district for which the report is generated.
            chart_infos (list): List of dictionaries containing information about each chart (title, base64 image data, description, statistics).
            report_text (str): Introductory text for the report.
            service (googleapiclient.discovery.Resource): Google Drive API service object.
            report_folder_id (str): ID of the Google Drive folder where the PDF will be uploaded.
            analysis_level (str): The level of analysis ('District' or 'SubDistrict').
            report_folder (str, optional): Path to the local report folder (used for debugging and development).
            report_title (str, optional): Title of the report (defaults to 'Default Report Title').

        Returns:
            str or None: The ID of the uploaded PDF file if successful, None otherwise.
        """

    # Iterate over chart information
    for chart_info in chart_infos:
        chart_data = {}
        chart_data.update(chart_info)

        # Check if the chart image data is already base64 encoded (from preview)
        if 'image_data' in chart_info:
            encoded_image = chart_info['image_data']
        elif 'file_id' in chart_info:
            # If not base64 encoded, fetch the image from Google Drive using its file ID
            request = drive_service.files().get_media(fileId=chart_info['file_id'])
            fh = io.BytesIO()     # Create a BytesIO object to store the downloaded image data
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            fh.seek(0)     # Reset the file pointer to the beginning

            # Encode the fetched image into base64
            encoded_image = base64.b64encode(fh.read()).decode('utf-8')
        else:
            print("Error: Neither image_data nor file_id found in chart_info")
            continue  # Skip this chart if no valid data is found

        # Add the base64 encoded image data to the chart_data dictionary
        chart_data['image_data'] = f"data:image/png;base64,{encoded_image}"
        modified_chart_infos.append(chart_data)
        print("modified chart info", modified_chart_infos)

    # Render the PDF template ('pdf_template.html') using Jinja2
    rendered_html = render_template('pdf_template.html',
                                    district=area,
                                    chart_infos=modified_chart_infos,
                                    report_text=report_text,
                                    report_folder=report_folder,
                                    os=os,
                                    report_title=report_title)  # Pass report_title to the template

    # Create a BytesIO object to hold the PDF data in memory
    pdf_file = io.BytesIO()

    print(rendered_html)

    # Convert the rendered HTML into a PDF using xhtml2pdf
    pisa_status = pisa.CreatePDF(rendered_html, dest=pdf_file, link_callback=link_callback)

    # Check if the PDF creation was successful
    if not pisa_status.err:
        # Create the file metadata for uploading to Google Drive
        pdf_filename = f"{area}_{analysis_level}_report.pdf"
        file_metadata = {'name': pdf_filename, 'parents': [report_folder_id]}

        # Create a MediaIoBaseUpload object to upload the PDF
        media = MediaIoBaseUpload(pdf_file, mimetype='application/pdf', resumable=True)

        # Upload the PDF to Google Drive
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f'PDF file {pdf_filename} uploaded to Google Drive with ID: {file.get("id")}')
        return file.get('id')  # Return the file ID
    else:
        print('Error creating PDF:', pisa_status.err)
        return None


def link_callback(uri, rel):
    """
    Convert URIs to absolute system paths to access resources.

    Parameters:
    uri -- The URI of the resource
    rel -- A relative URI reference

    Returns:
    Absolute system path of the resource.
    """
    import os.path
    from urllib.parse import urljoin, urlparse

    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    elif uri.startswith("file://"):
        return urlparse(uri).path
    if uri.startswith('charts/'):
        return os.path.join(app.static_folder, uri)

    return os.path.join(os.path.dirname(rel), uri)


def create_report_directory():
    """
        Creates a directory to store generated reports, with a unique timestamped subfolder.

        1. Defines the base directory for reports, combining the current working directory with 'phone_survey_reports'.
        2. Generates a timestamp string with the current date and time in the format 'YYYY-MM-DD_HH-MM-SS'.
        3. Creates a unique subfolder path by combining the base directory with the timestamp.
        4. Creates the directory (and any necessary parent directories) using `os.makedirs`.
           * The `exist_ok=True` parameter prevents errors if the directory already exists.
        5. Returns the full path to the newly created subfolder.

        Returns:
            str: The full path to the created report directory.
        """
    # Define the base directory for all reports
    reports_base_folder = os.path.join(os.getcwd(), 'phone_survey_reports')
    # Generate a timestamp string with the current date and time
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    # Create a unique subfolder name using the timestamp
    report_folder = os.path.join(reports_base_folder, f'report_{timestamp}')
    # Create the directory and any necessary parent directories
    os.makedirs(report_folder, exist_ok=True)
    # Return the full path to the created report directory
    return report_folder

def create_drive_folder(service, folder_name, parent_folder_id):
    """
        Creates a new folder in Google Drive.

        Args:
            folder_name (str): The name of the folder to create.
            parent_folder_id (str, optional): The ID of the parent folder.
                If not provided, the folder will be created in the root of My Drive.

        Returns:
            str: The ID of the newly created folder.

        Raises:
            googleapiclient.errors.HttpError: If the folder creation fails due to
                API issues or insufficient permissions.
        """

    # Prepare metadata for the new folder
    file_metadata = {
        'name': folder_name,            # Set the folder's name
        'mimeType': 'application/vnd.google-apps.folder',      # Indicate it's a folder
        'parents': [parent_folder_id]      # Set parent (optional)
    }
    # Attempt to create the folder
    try:
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')       # Return the ID of the created folder
    except HttpError as error:
        print(f'Error creating folder: {error}')     # Log the error
        return None    # Indicate failure by returning None


def upload_file_to_drive(service, file_path, folder_id, file_name, analysis_level):
    """
        Uploads a file to Google Drive, specifically a PNG or PDF, and renames it based on analysis level.

        Args:
            service: The authenticated Google Drive API service object.
            file_path (str): The local path to the file to be uploaded.
            folder_id (str): The ID of the Google Drive folder where the file should be placed.
            file_name (str): The original name of the file (including extension).
            analysis_level (str): A string indicating the level of analysis (used in the new filename).

        Returns:
            str: The ID of the uploaded file if successful, or None if an error occurred.

        Raises:
            ValueError: If the file extension is not supported (currently only PNG and PDF).
        """

    # Extract the file extension and convert to lowercase for comparison
    file_extension = file_name.split('.')[-1].lower()

    # Determine the appropriate MIME type based on the file extension
    if file_extension == 'png':
        mimetype = 'image/png'
    elif file_extension == 'pdf':
        mimetype = 'application/pdf'
    else:
        raise ValueError(f"Unsupported file extension: {file_extension}")

    # Prepare metadata for the uploaded file
    file_metadata = {
        'name': f"{file_name.split('.')[0]}_{analysis_level}.{file_extension}",
        'parents': [folder_id]
    }
    # Create a MediaFileUpload object to handle the file's content
    media = MediaFileUpload(file_path, mimetype=mimetype)
    # Attempt to upload the file
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return file.get('id')        # Return the file ID upon success
    except HttpError as error:        # Catch potential errors during the upload
        print(f'An error occurred: {error}')
        return None                  # Indicate failure by returning None


if __name__ == '__main__':
    app.run(port=8080, debug=True)

def link_callback(uri, rel):
    if uri.startswith('charts/'):
        return os.path.join(app.static_folder, uri)
    return ''

if __name__ == '__main__':
    app.run(debug=True)