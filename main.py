import os
from flask import Flask, render_template, request, redirect, session, url_for
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


mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial']

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)  # Generate a secure secret key
app.static_folder = 'static'  # Set the static folder

# Twilio configuration
account_sid = 'ACCOUNT_SID'
auth_token = 'AUTH_TOKEN'
twilio_phone_number = 'TWILIO_PHONE_NUMBER'
client = Client(account_sid, auth_token)



# Google Drive API configuration
creds = Credentials.from_authorized_user_file('credentials.json', ['https://www.googleapis.com/auth/drive'])
drive_service = build ('drive', 'v3', credentials=creds)


mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial']


def generate_chart(df, x_column, y_column, chart_type, chart_title, x_label, y_label, filename, threshold, chart_color):
    plot_data = None
    if chart_type == 'bar':
        plot_data = df.groupby(x_column)[y_column].sum()
        # Sort the plot data in ascending order
        plot_data = plot_data.sort_values()
    elif chart_type == 'line':
        plot_data = df.groupby(x_column)[y_column].sum()
    elif chart_type == 'pie':
        plot_data = df.groupby(x_column)[y_column].sum()

    # Generate plot with professional style
    plt.style.use('bmh')
    fig, ax = plt.subplots(figsize=(1.5, 1))  # Adjust the figure size here
    ax.set_facecolor('white')  # Set the plot background color

    if chart_type == 'pie':
        wedges, texts, autotexts = ax.pie(plot_data.values, labels=plot_data.index, autopct='%1.1f%%', startangle=90,
                                          textprops={'fontsize': 3})
        plt.setp(autotexts, size=2, weight='bold')
        ax.axis('equal')  # Equal aspect ratio ensures that the pie chart is drawn as a circle
        plt.legend(wedges, plot_data.index, loc='center left', bbox_to_anchor=(1.0, 0.5), fontsize=4)
    else:
        plot = plot_data.plot(kind=chart_type, ax=ax, color=chart_color)

        # Add horizontal line for threshold
        if threshold is not None and isinstance(threshold, (int, float)):  # Check if threshold is a valid number
            threshold_value = float(threshold)
            ax.axhline(y=threshold_value, color='r', linewidth=0.5, linestyle='--',
                       label=f'Threshold: {threshold_value}')
            ax.legend(loc='upper right', fontsize=2.5)

    ax.set_xlabel(x_label, fontsize=3, color='black')
    ax.set_ylabel(y_label, fontsize=3, color='black')
    # ax.set_title(chart_title, fontsize=4, fontweight='bold', color='black')

    # Add grid lines
    ax.grid(True, linestyle='--', linewidth=0.5, color='gray')

    # Adjust tick label font sizes and colors
    plt.xticks(fontsize=2.5, color='black')
    plt.yticks(fontsize=2.5, color='black')

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Create a 'charts' folder within the static directory if it doesn't exist
    charts_folder = os.path.join(app.static_folder, 'charts')
    os.makedirs(charts_folder, exist_ok=True)

    # Save the plot to the 'charts' folder
    plt.savefig(os.path.join(charts_folder, filename), bbox_inches='tight', dpi=300)
    plt.close()

@app.route('/')
def index():
    return render_template('index.html')



@app.route('/analyze', methods=['POST'])
def analyze():
    # Get uploaded files
    data_file = request.files['data_file']
    phone_numbers_file = request.files['phone_numbers_file']

    if data_file.filename != '' and phone_numbers_file.filename != '':
        # Read CSV files
        data_csv = data_file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(data_csv))


        phone_numbers_csv = phone_numbers_file.read().decode('utf-8')
        phone_numbers_df = pd.read_csv(io.StringIO(phone_numbers_csv))

        column_names = df.columns.tolist()

        # Get unique district values
        districts = df['District'].unique()

        # Get selected columns and additional information for each chart
        num_charts = int(request.form['num_charts'])
        chart_configs = []
        for i in range(num_charts):
            x_column = request.form[f'x_column_{i + 1}']
            y_column = request.form[f'y_column_{i + 1}']
            chart_type = request.form[f'chart_type_{i + 1}']
            chart_title = request.form[f'chart_title_{i + 1}']
            x_label = request.form.get(f'x_label_{i + 1}', '')  # Use get() to handle missing keys
            y_label = request.form.get(f'y_label_{i + 1}', '')  # Use get() to handle missing keys
            description = request.form.get(f'description_{i + 1}', '')  # Use get() to handle missing keys
            threshold_str = request.form.get(f'threshold_{i + 1}', '')  # Use get() to handle missing keys
            threshold = None
            if threshold_str.strip():  # Check if the string is not empty
                try:
                    threshold = float(threshold_str)
                except ValueError:
                    pass  # Ignore if the conversion to float fails

            chart_color = request.form.get(f'chart_color_{i + 1}', '#61a673')

            # Filters
            filters = []
            filter_count = 1
            while f'filter_action_{i}_{filter_count}' in request.form:
                filter_action = request.form[f'filter_action_{i}_{filter_count}']
                filter_column = request.form[f'filter_column_{i}_{filter_count}']
                filter_type = request.form[f'filter_type_{i}_{filter_count}']
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

        # Get the report text from the form data
        report_text = request.form.get('report_text', '')

        # Generate charts and send PDFs for each district
        for district in districts:
            district_df = df[df['District'] == district]
            chart_infos = []

            for config in chart_configs:
                for config in chart_configs:
                    filtered_data = district_df.copy()
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

                x_column = config['x_column']
                y_column = config['y_column']
                chart_type = config['chart_type']
                chart_title = config['chart_title']
                x_label = config['x_label']
                y_label = config['y_label']
                description = config['description']
                threshold = config['threshold']
                chart_color = config['chart_color']
                filename = f"{district}_{x_column}_{y_column}.png"

                # Calculate min, max, avg, mode, and median for the y_column
                y_column_data = district_df[y_column]
                min_value = y_column_data.min()
                max_value = y_column_data.max()
                avg_value = y_column_data.mean()
                mode_value = y_column_data.mode().iloc[0]  # Assuming the mode is unique
                median_value = y_column_data.median()

                generate_chart(district_df, x_column, y_column, chart_type, chart_title, x_label, y_label, filename, threshold, chart_color)

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
                    'median_'+ y_column: median_value,
                    'y_column': y_column
                })

            # Create and upload PDF for the district
            pdf_filename = f"{district}_report.pdf"
            create_pdf(pdf_filename, district, chart_infos, report_text)
            file_url = upload_to_drive(pdf_filename)

            # Send SMS to phone numbers associated with the district
            district_phone_numbers = phone_numbers_df[phone_numbers_df['District'] == district]['phone_no']
            send_sms(district_phone_numbers, file_url)

        # Render the index template with the column names
        return render_template('index.html', column_names=column_names)

    else:
        return 'Files missing'
def create_pdf(filename, district, chart_infos, report_text):
    # Render the pdf_template.html template with the chart information and report_text
    rendered_html = render_template('pdf_template.html', district=district, chart_infos=chart_infos, report_text=report_text)

    # Create a PDF from the rendered HTML
    pdf = io.BytesIO()
    pisa_status = pisa.CreatePDF(rendered_html, dest=pdf, link_callback=link_callback)

    # Check if the PDF creation was successful
    if pisa_status.err:
        raise Exception('Error creating PDF')

    # Save the PDF to a file
    with open(filename, 'wb') as f:
        f.write(pdf.getvalue())

def upload_to_drive(filename):
    # Upload the PDF file to Google Drive
    file_metadata = {'name': filename}
    with open(filename, 'rb') as file:
        media = MediaIoBaseUpload(file, mimetype='application/pdf', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')

    # Set the file permissions to make it publicly accessible
    permission = {'type': 'anyone', 'role': 'reader'}
    drive_service.permissions().create(fileId=file_id, body=permission).execute()

    # Get the public URL of the uploaded file
    file_url = f"https://drive.google.com/uc?id={file_id}"
    return file_url


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

def shorten_url(url):
    # Use a URL shortener service to shorten the download link
    # Example: Using the Bitly URL shortener (sign up for an account and get an access token)
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

def link_callback(uri, rel):
    if uri.startswith('charts/'):
        return os.path.join(app.static_folder, uri)
    return ''


if __name__ == '__main__':
    app.run(debug=True)