import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import psycopg2
from io import BytesIO

# General Variables
s3_bucket = 'poc-toluna'

# Establish the connection to S3 -
# expose after uploading the files to lambda
s3 = boto3.client('s3')

# Specify your AWS credentials and region
# Remove after uploading the files to lambda
# aws_access_key_id = 'AKIAZ56AN5CHLY6KLKCU'
# aws_secret_access_key = 'eXAiprqxyQF49nkoVrT8mhvRzPZ8Qj2fuz5Jw7hF'
# aws_region = 'eu-west-1'
#
# # Establish the connection to S3
# s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_region)


# Establish the connection to Redshift
redshift_host = 'redshift-sandbox.cqbdyi9dryca.us-east-1.redshift.amazonaws.com'
redshift_db = 'dev'
redshift_user = 'awsuser'
redshift_password = 'AwsuserAwsuser1'
redshift_port = '5439'
redshift_schema = 'public'

conn = psycopg2.connect(
    host=redshift_host,
    dbname=redshift_db,
    user=redshift_user,
    password=redshift_password,
    port=redshift_port
)


def select_records(cursor, redshift_table):
    query = f"SELECT * FROM {redshift_table}"
    cursor.execute(query)
    # Fetch all the rows returned by the query
    rows = cursor.fetchall()
    # Get the column names from the cursor description
    column_names = [desc[0] for desc in cursor.description]
    # Create a DataFrame using the fetched rows and column names
    data = pd.DataFrame(rows, columns=column_names)
    return data


def insert_records(cursor, row, redshift_table, columns):
    # Create a string with columns name
    column_string = '(' + ', '.join(columns) + ')'
    value_string = create_string_value(row)
    query = f"INSERT INTO {redshift_schema}.{redshift_table} {column_string} VALUES {value_string}"
    # query = f"INSERT INTO dev.public.dimscenario (scenarioname) VALUES ('sss')"
    print(query)
    cursor.execute(query)


def update_records(cursor, data, redshift_table):
    for index, row in data.iterrows():
        # Assuming the table has columns: col1, col2, col3
        query = f"UPDATE {redshift_table} SET col1 = '{row['col1']}', col2 = '{row['col2']}' WHERE col3 = '{row['col3']}'"
        cursor.execute(query)


def delete_records(cursor, data, redshift_table, column_name_arr):
    for index, row in data.iterrows():
        # Assuming the table has columns: col1, col2, col3
        query = f"DELETE FROM {redshift_table} WHERE col1 = '{row['col1']}'"
        cursor.execute(query)


def create_string_value(row):
    # Create a list to store the column values for the current row
    values = []

    # Iterate over each column value in the current row
    for column_name, value in row.items():
        # Add the formatted column value to the list
        values.append("'" + str(value) + "'")

    # Create the string with the desired structure for the current row
    row_string = "(" + ", ".join(values) + ")"
    return row_string


def lambda_handler(event, context):

    cursor = conn.cursor()

    # Iterate through the S3 bucket
    response = s3.list_objects_v2(Bucket=s3_bucket, Prefix='intermediate/')

    for obj in response['Contents']:
        key = obj['Key']
        if key.endswith('.parquet'):

            # Extract source_table, year, month, and day from the key. sample intermediate/source_table/year=yyyy/month=mm/day=dd/file_name.parquet
            stage, source_table, year, month, day, file_name = key.split('/')

            # Skip initial content
            if "LOAD" in file_name:
                print(key, 'Contains an initial content, Skip on that..')
                continue

            # Load the Parquet file into a Pandas DataFrame
            s3_object = s3.get_object(Bucket=s3_bucket, Key=key)
            parquet_file = pq.ParquetFile(BytesIO(s3_object['Body'].read()))
            table = parquet_file.read()
            df = table.to_pandas()
            # Get the column names of the DataFrame, Exclude the first and the second columns (first = action, second= primary key)
            source_columns = df.columns[2:]
            print('Columns name: ', source_columns)

            # Define a loop to iterate over each row
            for index, row in df.iterrows():
                # Perform the appropriate action based on the source table
                # The assumption is that the first column is the action and the second is the primary key
                if row[0] == 'I':
                    # Drop column 'Op' from the DataFrame
                    print('The action is: ', row[0])
                    print('The primary key is: ', row[1])
                    print('The record content is (before modifying): ', row)
                    print('The record content is (after modifying): ', row[2:])
                    insert_records(cursor, row[2:], source_table, source_columns)
                # elif row[0] == 'U':
                #     update_records(cursor, df, table)
                # elif row[0] == 'D':
                #     delete_records(cursor, df, table)

            # Commit the changes to Redshift
            conn.commit()

    # Close the connection to Redshift
    conn.close()