# Week 11 실습 · AWS Lambda 미니 드라이브

AWS 웹 콘솔과 브라우저에서 파일 업로드·목록 조회·다운로드를 연결하는 실습입니다. S3 버킷 1개, Lambda 함수 1개, HTTP API 1개, CloudFront 배포 1개를 사용합니다. 지역 리소스는 수업에서 지정한 같은 리전에 만듭니다.

## 코드 받기

1. [week11-practice](https://github.com/Mok2Lee/week11-practice)에서 **Code → Download ZIP**을 선택합니다.
2. ZIP 압축을 풀고 `week11-practice-main` 폴더를 VS Code에서 엽니다.

Git을 사용하는 경우 PowerShell에서 아래 명령을 실행하고 `week11-practice` 폴더를 VS Code에서 엽니다.

```powershell
git clone https://github.com/Mok2Lee/week11-practice.git
```

## 제공 파일

- `lambda/lambda_function.py` — 파일 API와 S3 이벤트 처리 코드
- `web/` — 웹 화면 4개 파일. `config.js`에 HTTP API 호출 URL 입력
- `settings/` — Lambda의 실행역할 정책, CloudFront의 S3 버킷 정책, S3 CORS 설정
- `demo.txt` — 업로드와 다운로드에 사용할 샘플 파일

## 1. S3 버킷, 전용 역할, Lambda 함수 만들기

1. **S3 → 범용 버킷 → 버킷 만들기**에서 Lambda와 같은 리전을 선택합니다. **글로벌 네임스페이스**의 고유한 버킷 이름을 사용하고 **모든 퍼블릭 액세스 차단**을 유지합니다. 버전 관리는 비활성화, 암호화는 기본 SSE-S3를 선택합니다.
2. **IAM → 역할 → 역할 생성 → AWS 서비스 → Lambda → 다음**으로 이동합니다. 권한 추가 화면에서 정책 선택 없이 **다음**을 누르고, 역할 이름을 `week11-drive-role`로 입력해 생성합니다.
3. VS Code에서 `settings/runtime-policy.json`을 열고 `Ctrl+H`의 **모두 바꾸기**로 아래 값을 각각 치환합니다. 역할 상세에서 **권한 추가 → 인라인 정책 생성 → JSON**에 수정한 JSON을 입력하고 **다음 → 정책 이름 `week11-drive-runtime` → 정책 생성**을 선택합니다. 역할 상세의 권한 정책 1개를 확인합니다.

   | 치환할 문자열 | 실제 입력값 |
   | --- | --- |
   | `FILES_BUCKET_NAME` | 실습 버킷 이름 |
   | `AWS_REGION` | 실습 리전 코드 |
   | `AWS_ACCOUNT_ID` | 콘솔에 표시된 본인 계정 ID 12자리 |
   | `FUNCTION_NAME` | 만들 함수 이름. 예: `week11-drive` |

   이 정책으로 지정 버킷의 `incoming/` 목록·객체와 지정 함수의 로그에만 접근할 수 있습니다.

4. **Lambda 함수 생성 및 실행 역할 연결**

   1. AWS 콘솔에서 실습 리전을 선택한 뒤 **Lambda → Event Functions → Create Event Function → 새로 작성**을 엽니다. **기본 정보**에 3단계의 `FUNCTION_NAME`과 같은 함수 이름을 입력하고 런타임은 **Python 3.13**을 선택합니다.
   2. 같은 화면에서 아래로 내려 **사용자 지정 설정 → 추가 설정**을 펼치고 **사용자 지정 실행 역할**을 켭니다.
   3. **역할 생성** 패널에서 **Permissions → Use existing role**을 선택합니다. **Select role → Choose a role** 목록에서 앞서 만든 `week11-drive-role`을 선택하고 패널의 **Save**를 누릅니다.
   4. 함수 생성 화면 맨 아래의 **Create Event Function**을 누릅니다.
   5. 함수가 열리면 **구성 → 권한 → 실행 역할**에서 연결한 역할 이름을 확인합니다. **구성 → 일반 구성 → 편집**에서 제한 시간을 **10초**로 설정하고 저장합니다.

   생성 화면에 **권한 → 기본 실행 역할 변경**이 표시되는 경우에는 그 메뉴를 펼쳐 **기존 역할 사용**에서 같은 역할을 고른 뒤 함수를 생성합니다.
5. `lambda/lambda_function.py`의 `log_upload`에서 `key = ''`와 `size = 0`을 아래 두 줄로 바꿉니다.

   ```python
   key = unquote_plus(obj['key'])
   size = obj['size']
   ```

6. `lambda_function.py` 파일을 직접 선택해 ZIP으로 압축합니다. ZIP을 열면 `lambda_function.py`가 최상위에 보여야 합니다. **Lambda → 코드 → 코드 소스 → 업데이트 → .zip 파일에서 업데이트 → 파일 선택 → 업데이트**를 선택합니다.
7. **구성 → 환경 변수 → 편집**에서 아래 값을 추가하고 저장합니다.

   | 키 | 값 |
   | --- | --- |
   | `FILES_BUCKET` | 실제 버킷 이름 |
   | `DRIVE_CODE` | 팀에서 정한 임의의 영문·숫자 24자 이상. Lambda와 브라우저 입력란에서만 사용 |
   | `URL_TTL_SECONDS` | `120` |

8. **Lambda → 트리거 추가 → S3**에서 버킷을 선택합니다. 이벤트 유형은 **모든 객체 생성 이벤트**, 접두사는 `incoming/`입니다. 재귀 호출 안내를 확인하고 **추가**를 누릅니다. 함수의 업로드 이벤트 처리는 객체 정보를 로그에 기록합니다.

## 2. API Gateway 연결 및 요청량 설정

1. **API Gateway → API 생성 → HTTP API → 구축**에서 Lambda 통합을 추가하고 함수 `week11-drive`를 선택합니다. 통합 요청 페이로드 버전은 **2.0**입니다.
2. 다음 라우트 3개를 만들고 모두 같은 통합에 연결합니다. 생성 마법사의 기본 경로를 추가한 경우 아래 경로로 바꿉니다. `$default` 스테이지와 자동 배포를 사용합니다. 팀 코드는 Lambda 코드에서 검사합니다.

   | 메서드 | 경로 |
   | --- | --- |
   | POST | `/files/upload-url` |
   | GET | `/files` |
   | GET | `/files/{id}/download-url` |

3. API 왼쪽 메뉴의 **조절 중(Throttling)**에서 `$default` 스테이지를 선택합니다. **기본 경로 조절 → 편집**에서 **버스트 제한 1, 요율 제한 1**을 입력하고 **저장**합니다. 일반 기능 확인은 한 번씩 실행하고, 요청량 비교는 별도 버튼으로 한 번에 보냅니다.
4. 스테이지의 **호출 URL**을 복사해 `web/config.js`의 `apiBase`에 붙여넣습니다. 끝에 `/files`를 붙이지 않습니다.

## 3. CloudFront와 브라우저 주소 설정

1. S3에서 `site` 폴더를 생성합니다. 폴더 안에 `web/`의 `index.html`, `style.css`, `app.js`, `config.js` 네 파일을 직접 업로드합니다.
2. **CloudFront → 배포 생성 → 단일 웹 사이트 또는 앱**에서 S3를 원본 유형으로 선택합니다. 원본은 실습 버킷, 원본 경로는 `/site`입니다. **CloudFront에 대한 프라이빗 S3 버킷 액세스 허용**을 선택합니다. 배포 생성 후 원본 탭에서 원본 접근 제어(OAC)가 연결됐는지 확인합니다. 브라우저 접속은 `https://` 주소를 사용합니다. 기본 루트 객체 입력란이 생성 화면에 없다면 **배포 → 일반 → 설정 편집**에서 `index.html`을 입력합니다. Web Application Firewall(WAF) 선택 화면이 있는 경우 이 실습에서는 선택하지 않습니다.
3. `settings/site-policy.json`에 실제 `BUCKET_NAME`과 **CloudFront 배포 ARN**을 입력합니다. **S3 → 권한 → 버킷 정책**에 저장하여 이 배포에 `site/*` 읽기를 허용합니다. CloudFront 생성 마법사가 정책을 자동으로 등록한 경우에도 제공 정책의 `site/*` 범위로 수정합니다.
4. CloudFront 도메인 앞에 `https://`를 붙여 브라우저 출처를 기록합니다. 마지막 `/` 없이 두 곳에 입력합니다.

   - **API Gateway → CORS** — 허용 출처 `https://<CloudFront 도메인>`, 메서드 `GET, POST, OPTIONS`, 헤더 `Authorization, Content-Type`
   - **S3 → 권한 → CORS** — `settings/files-cors.json`에서 `CLOUDFRONT_ORIGIN`을 같은 주소로 바꾼 뒤 저장

5. CloudFront 배포의 설정 반영이 끝나면 배포 도메인을 브라우저에서 엽니다. `config.js`를 다시 올렸는데 이전 주소를 사용하는 경우 **CloudFront → 무효화 → `/config.js`**를 적용한 뒤 새로고침합니다.

## 4. 파일 기능과 요청량 확인

1. 브라우저에서 팀 코드 입력 → **드라이브 열기** → 목록 `200` 확인
2. `demo.txt` 선택 → **업로드** → `S3 업로드 200` 확인
3. **목록 조회** → `demo.txt`와 `66 B` 확인 → **다운로드** → 받은 파일과 제공된 `demo.txt`를 텍스트 편집기로 각각 열어 두 줄 비교
4. **Lambda → 모니터링 → CloudWatch 로그 보기** → 업로드 시각의 로그 스트림 → `upload_received`의 `key`와 `bytes: 66` 확인
5. 브라우저 개발자 도구의 **Network(네트워크)**를 연 뒤 **목록 요청 24건 보내기**를 한 번 클릭합니다. `GET /files`의 `200`과 `429`를 비교합니다. 앱에서 상태 코드를 읽을 수 없으면 Network 탭에서 확인합니다. 요청이 흩어져 모두 성공하면 잠시 기다린 뒤 다시 한 번 클릭합니다.

### 점검 위치

| 화면 | 확인 항목 |
| --- | --- |
| CloudFront `403` | 배포 반영 여부, `site/index.html`, 원본 경로 `/site`, S3 버킷 정책의 배포 ARN |
| 목록 `401` | Lambda 환경 변수 `DRIVE_CODE`와 화면에 입력한 팀 코드의 일치 |
| 브라우저 요청 오류 | 개발자 도구 Network의 실패 주소, API Gateway 또는 S3 CORS의 허용 출처 |
| 업로드 후 로그 누락 | S3 트리거 접두사 `incoming/`, 함수 코드 Deploy, 로그 기록 권한 |

## 5. 실습 리소스 정리

1. API Gateway의 실습 HTTP API를 삭제합니다. CloudFront 배포는 **비활성화**한 뒤 반영 대기를 시작합니다.
2. 실습 S3의 이벤트 알림과 Lambda 함수, 해당 CloudWatch 로그 그룹, 실습용 IAM 실행 역할 및 추가한 정책을 정리합니다.
3. CloudFront 배포 비활성화 반영 후 배포와 사용하지 않는 실습 OAC를 삭제합니다.
4. 실습 S3 버킷을 비운 뒤 버킷을 삭제합니다. 이 실습의 데모 파일과 리소스만 선택합니다.
