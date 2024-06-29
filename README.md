# Report_Generator

## Assumptions

- The dataset is assumed to be well known by the user (say CEGIS staff or dedicated PoC at dept) i.e., they are aware of what the column names in their dataset imply
- The dataset is cleaned, if needed, by the user already.
- The respective District and Sub-District columns are named as ‘District’ and ‘SubDistrict’ in both of the datasets to ensure compatibility with the code. 
- There are no coded categorical variables in the dataset and have been converted to the text that they imply, if present. For example, if there are coded values like 0 and 1 where 0 implies 'Didn't pick up phone' and 1 implies 'Picked up by expected receiver', then 0 and 1 should be replaced with their values themselves.
- The data file and phone numbers file are in .csv format as shown in the template provided. Templates can be found here: Survey dataset, Phonebase.
- The user has checked and is aware of what data types(numeric or categorical) must go into corresponding charts (bar, pie, scatter, line).


## Steps for usage

### Running the code on your local machine

To run the code on your local machine, one is required to install Python onto their computer and an IDE for the same (I used Pycharm-Community Edition). Configure the Python interpreter on your IDE (refer to the installation guide of your corresponding IDE from the internet) . 
Next, clone the Github repository and open the main.py code in your IDE. Make sure the directory hierarchies remain the same as in the Github repository. There are certain packages that need to be installed for running the code. These are as follows: 
- Flask==2.3.2
- pandas==1.5.3
- matplotlib==3.7.1
- xhtml2pdf==0.2.8
- twilio==7.16.1
- google-api-python-client==2.72.0
- google-auth-httplib2==0.1.0
- google-auth-oauthlib==1.0.0
- Jinja2==3.1.2
- pdfkit==1.0.0
- wkhtmltopdf==0.12.6  # Version might differ based on your OS

As an example, you can install these by typing 'pip install Flask==2.3.2' or just 'pip install Flask' into your Python IDE terminal. The latter will install the latest version of any package but in some cases, might not be compatible. 
To install it all in one go, you can enter this pre-written command into your IDE terminal: 
```bash
pip install Flask pandas matplotlib xhtml2pdf twilio google-auth google-auth-oauthlib google-api-python-client requests pdfkit Jinja2
```
Obtain the credentials file(it is not available on github repository) and place it in the same directory as main.py. And replace the twilio credentials in main.py with your credentials:
```bash
account_sid = ' '
auth_token = ' '
twilio_phone_number = '+ '
client = Client(account_sid, auth_token)
```

After the packages have been installed, one can run the code. The local URL will become displayed and will mostly be either http://127.0.0.1:5000 or http://127.0.0.1:8080. Open this URL to access the website portal. 

### Using the website

Once the website has been loaded, one will encounter the instructions page which will include the instructions to use the website. These are as follows:
- Upload data and wait for few seconds for the data file to be uploaded and the first chart to appear.
- Upload the phone number dataset.
- Select whether you want to perform the analysis District-wise or Sub District-wise.
- Enter the introduction/ context to the report under Report Text. 
- Enter the details that will be required to plot the chart.
- Enter the X column, Y column, Chart Type.
- Next give the chart a title and X and Y axis labels. 
- Under Description, enter a general description for the chart and the relationship between X and Y columns. 
- In case of a benchmark value for a certain Y column, one can set a threshold value which will mark a threshold line on the plot. This is not applicable for pie charts and shouldn't be given as input. 
- Chart color can be selected under ‘Chart Color’ and the Legend text under ‘Legend Label’. 
- Next is a very important feature which is a filter based on a particular condition that the data records fulfill or do not fulfil. 
- Action can take two values: Keep, Drop. 
- Selecting keep, one can run the analysis only for the data that meets the condition mentioned in this section. 
- If one selects drop, then the data records satisfying the condition are excluded from the analysis. 
- To set a condition. one needs to select a particular column name and the type of filter we are applying: Text ( for textual/ categorical variables) or Range( for numerical variables). 
- This is followed by selected the value of range itself( minimum and maximum).
- A convenient feature of the webpage is that one can save their entered preferences and inputs to use later if the same file is uploaded again. 
- The user can save a preset by clicking on the button Save Preset. 
- When the user uploads the file next time, they can directly go to the bottom of the page and select a preset from the list of saved presets under Load Preset. 
- User can preview the report for one of the districts or sub-districts before deciding to save it to drive and sending it via SMS. 
- Next user can choose to either just save the files to the fixed drive folder or also send a link to its download to the incharges at those administrative levels 

## Present challenges and pending areas

There are some challenges currently that might require the user to exercise some caution while using the product. These are:

- The information filled in the portal form is lost once the person clicks on 'save to drive', 'send report as SMS' or 'preview report' button. Hence it is advisable to make use of the preset feature for and re-uploading the dataset for some ease. 
- The pie chart may sometimes not generate the expected output due to it taking in extra parameters like X and Y axis labels, threshold and color.
- There is not yet an option of selecting custom colors for each component in a chart. Hence it will pick either a single color that was selected in the form or select some other pre-saved color. 
- There's a lack of enough error handling currently in the portal. For example, in case of selection of wrong data type, there's no error message that is displayed to let the user know what was wrong in their input. 
- There's a lack of confirmative flash messages to let the user know whether a task has been successful or not. For example, after saving the files to drive, there's no message displayed. 
- The label text function might not be leading to expected outcomes currently.








