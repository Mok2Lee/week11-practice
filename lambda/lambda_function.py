import base64
from datetime import datetime
import json
import os
import re
from secrets import compare_digest
from urllib.parse import quote, unquote_plus
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


REGION = os.environ['AWS_REGION']
s3 = boto3.client('s3', endpoint_url=f'https://s3.{REGION}.amazonaws.com',
                  config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))
BUCKET = os.environ['FILES_BUCKET']
EXPIRES = int(os.environ.get('URL_TTL_SECONDS', '300'))
MAX_BYTES = 10 * 1024 * 1024
TEAM_CODE = os.environ['DRIVE_CODE']
PREFIX = 'incoming/'
FILE_ID = re.compile(r'[0-9a-f]{32}--[^/\\\x00-\x1f\x7f]+')


def response(status, **body):
    return {
        'statusCode': status,
        'headers': {'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store'},
        'body': json.dumps(body, ensure_ascii=False),
    }


def list_files(prefix, query):
    options = {'Bucket': BUCKET, 'Prefix': prefix, 'MaxKeys': 50}
    if query.get('page'):
        options['ContinuationToken'] = query['page']
    result = s3.list_objects_v2(**options)
    files = []
    for item in result.get('Contents', []):
        file_id = item['Key'][len(prefix):]
        if not FILE_ID.fullmatch(file_id):
            continue
        modified: datetime = item['LastModified']
        files.append({'id': file_id, 'name': file_id.split('--', 1)[1],
                      'size': item['Size'], 'uploadedAt': modified.isoformat()})
    return response(200, files=files, nextPage=result.get('NextContinuationToken'))


def upload_url(prefix, event):
    raw = event.get('body') or '{}'
    if event.get('isBase64Encoded'):
        raw = base64.b64decode(raw, validate=True)
    data = json.loads(raw)
    if not isinstance(data, dict):
        return response(400, message='파일 정보가 필요합니다.')
    name = data.get('name')
    size = data.get('size')
    if (not isinstance(name, str) or not name.strip() or name in {'.', '..'}
            or not FILE_ID.fullmatch(f'{uuid4().hex}--{name}') or len(name.encode('utf-8')) > 180):
        return response(400, message='유효한 파일 이름을 입력하세요.')
    if type(size) is not int or not 1 <= size <= MAX_BYTES:
        return response(400, message='1바이트부터 10MiB까지 업로드할 수 있습니다.')
    file_id = f'{uuid4().hex}--{name}'
    content_type = 'application/octet-stream'
    url = s3.generate_presigned_url('put_object', Params={
        'Bucket': BUCKET, 'Key': prefix + file_id, 'ContentType': content_type,
        'ContentLength': size, 'IfNoneMatch': '*',
    }, ExpiresIn=EXPIRES)
    return response(200, url=url, headers={'Content-Type': content_type, 'If-None-Match': '*'})


def download_url(prefix, file_id):
    if not FILE_ID.fullmatch(file_id):
        return response(400, message='파일 주소가 올바르지 않습니다.')
    name = file_id.split('--', 1)[1]
    s3.head_object(Bucket=BUCKET, Key=prefix + file_id)
    url = s3.generate_presigned_url('get_object', Params={
        'Bucket': BUCKET, 'Key': prefix + file_id,
        'ResponseContentDisposition': f"attachment; filename*=UTF-8''{quote(name, safe='')}",
        'ResponseContentType': 'application/octet-stream',
    }, ExpiresIn=EXPIRES)
    return response(200, url=url)


def log_upload(event):
    for record in event['Records']:
        obj = record['s3']['object']
        # 실습: obj['key'] 디코딩 및 obj['size'] 읽기
        key = ''
        size = 0
        print(json.dumps({'event': 'upload_received', 'key': key, 'bytes': size}, ensure_ascii=False))


def lambda_handler(event, context):
    if 'Records' in event:
        log_upload(event)
        return
    if event.get('Event') == 's3:TestEvent':
        return
    auth = (event.get('headers') or {}).get('authorization', '')
    if not TEAM_CODE or not compare_digest(auth.encode('utf-8'), f'Bearer {TEAM_CODE}'.encode('utf-8')):
        return response(401, message='팀 실습 코드를 확인하세요.')
    route = event.get('routeKey')
    try:
        if route == 'GET /files':
            return list_files(PREFIX, event.get('queryStringParameters') or {})
        if route == 'POST /files/upload-url':
            return upload_url(PREFIX, event)
        if route == 'GET /files/{id}/download-url':
            return download_url(PREFIX, (event.get('pathParameters') or {}).get('id') or '')
        return response(404, message='등록된 경로가 아닙니다.')
    except (ValueError, UnicodeError):
        return response(400, message='요청 형식을 확인하세요.')
    except ClientError as error:
        code = error.response.get('Error', {}).get('Code', '')
        if code in {'404', 'NotFound', 'NoSuchKey'} or (route == 'GET /files/{id}/download-url' and code in {'403', 'AccessDenied'}):
            return response(404, message='파일을 찾을 수 없습니다.')
        if code in {'InvalidArgument', 'InvalidToken'} and route == 'GET /files':
            return response(400, message='목록을 새로고침하세요.')
        print(json.dumps({'event': 's3_error', 'route': route, 'code': code}))
        return response(502, message='S3 요청을 처리하지 못했습니다.')
