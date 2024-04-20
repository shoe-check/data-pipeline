from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.s3 import S3
from pandas import DataFrame
from os import path
from minio import Minio
from io import StringIO, BytesIO
import pandas as pd
import zlib
from datetime import date
import boto3
from botocore.client import Config


if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


def create_bucket(minio_client,bucket_name):
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

@data_exporter
def export_data_to_s3(df_split1: DataFrame,df_split2: DataFrame,df_split3: DataFrame, **kwargs) -> None:
    """
    Template for exporting data to a S3 bucket.
    Specify your configuration settings in 'io_config.yaml'.

    Docs: https://docs.mage.ai/design/data-loading#s3
    """
    # config_path = path.join(get_repo_path(), 'io_config.yaml')
    # config_profile = 'default'

    brand_name = kwargs['GOAT_BRAND_NAME']
    date_stamp= date.today().isoformat()


    print('GOAT_BRAND_NAME',brand_name)

    minio_client = Minio(
        "10.10.0.50:6000",
        access_key=kwargs['s3AccessKey'],
        secret_key=kwargs['s3SecretKey'],
        secure=False  # Change to True if using HTTPS
    )

    create_bucket(minio_client,"sst-data-crawler")

    csv_buffer = StringIO()

    df = pd.concat([df_split1,df_split2,df_split3],ignore_index=True)
    
    df_bytes = df.to_csv(index=False).encode()
    compressed_data = zlib.compress(df_bytes,level=7)
    # print(csv_buffer.getvalue())
    
    

    s3 = boto3.client('s3', endpoint_url="http://10.10.0.50:6000", aws_access_key_id=kwargs['s3AccessKey'],
                  aws_secret_access_key=kwargs['s3SecretKey'])
    
    s3.upload_fileobj(BytesIO(compressed_data), "sst-data-crawler", f"raw/text/listing/goat/brand/{brand_name}/{date_stamp}/listings.gz")
    # minio_client.put_object("sst-data-crawler", f"raw/text/listing/goat/brand/{brand_name}", BytesIO(compressed_data),len(compressed_data),content_type="application/octet-stream",)
    decompressed_data = None

    try:
    # Decode the decompressed bytes to string and create a Pandas DataFrame
        response = s3.get_object(Bucket="sst-data-crawler", Key=f"raw/text/listing/goat/brand/{brand_name}/{date_stamp}/listings.gz")

    # Read the compressed data from the response
        compressed_data = response['Body'].read()

        decompressed_data = zlib.decompress(compressed_data)
        

    except Exception as e:
        print(e)

    df = pd.read_csv(BytesIO(decompressed_data))

    print('DataFrame from decompressed data:')
    print(df)
    return df

    # S3.with_config(ConfigFileLoader(config_path, config_profile)).export(
    #     df,
    #     bucket_name,
    #     object_key,
    # )
