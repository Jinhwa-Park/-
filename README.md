# 레시피 가격 측정기

요리와 인분을 입력해 강남 음식점의 게시 가격 또는 등록 레시피에 기반한 실험용 오퍼를 계산한다. 메뉴별 재료와 포장 단가를 사용하며, 가격을 산출할 근거가 부족하면 확인이 필요한 이유를 표시한다. 주문 시 외부 API 호출은 없다.

## 서울 가격표로 메뉴와 오퍼 조회

프로젝트의 `seoul-menu-prices-cleaned.xlsx`로 브라우저에서 바로 열 수 있는 내부 실험 화면을 만든다.

```sh
python3 -m pip install openpyxl
mkdir -p local
python3 lookup.py --seoul-workbook ~/Downloads/seoul-menu-prices-cleaned.xlsx local/menu-price-offers.html
```

`local/menu-price-offers.html`에서 메뉴명과 주문 인분을 입력하면 동일·유사 메뉴의 참고가, 판매 단위, 표본 유형, 매장 수, 관측 지역을 확인할 수 있다. 동일 메뉴의 일반 매장 2곳 이상에서 확인된 1인 단품 참고가를 우선 적용한다. 메뉴명 뒤의 `1인분`은 1인 단품을 가리키며 주문 인분은 별도 입력값을 사용한다. 가격표가 통상 1인 단품으로 분류한 메뉴의 인분 미표기 가격도 계산 근거에 그 구분을 표시한다. `1.5인분`, `500g` 등 별도 판매 규격은 게시 가격을 참고용으로 표시한다. 유사 메뉴는 판매 규격을 맞춘 같은 요리 유형에서 최대 3종을 골라 메뉴별 참고가의 중앙값으로 추정한다. 주재료 유형을 파악할 수 있으면 같은 유형의 메뉴를 사용한다. 유사 메뉴 시세는 비교용 참고가로 표시하며 오퍼는 보류한다.

실험용 오퍼는 전체 주문 기준가의 −8%~−4%, −2%~+2%, +4%~+8% 구간에서 하나씩 뽑는다. 각 구간에 100원 단위 금액이 있으면 그 중에서 선택한다. 조회를 다시 제출하면 새 오퍼가 생성된다. 생성한 HTML에는 가격표가 포함되어 `local/`에 보관한다.

### 시세와 원재료·레시피 견적 비교

`fried_rice.json`은 새우볶음밥과 새우계란볶음밥을 지원한다. `recipes.json`은 김치·스팸김치·참치·게살볶음밥, 된장찌개, 달걀국, 쇠고기미역국의 레시피와 추가 재료 단가를 제공한다. 추가 레시피는 먼저 재료비와 가산액을 보여주고, 작업시간을 입력하면 인건비와 총액을 표시한다.

**실측 작업시간·실제 매입가 입력**을 열면 주문당 준비·정리 시간, 한 번 조리할 때의 직접 작업시간과 인분, 주재료의 실제 구매 금액과 손질 후 사용 가능량을 입력할 수 있다. 작업시간은 준비·정리 시간에 조리 횟수와 1회 작업시간의 곱을 더한다. 주재료비는 실구매 금액을 사용 가능량으로 나눈 단가에 레시피 사용량을 곱해 계산한다. 입력값은 현재 조회에 적용된다. 화면에는 재료비, 인건비, 용기비, 재료비 가산액과 각 단가의 근거가 표시된다.

동일 메뉴 시세가 있으면 그 가격으로 오퍼를 생성하고 레시피 견적을 같은 주문 인분 기준으로 비교한다. 동일 메뉴 시세가 없으면 레시피 견적을 잠정가로 표시한다. 직접 작업시간과 주재료 매입 정보를 입력하고 레시피 재료와 분량을 확인하면 잠정가로 실험용 오퍼를 생성한다. 메뉴와 인분을 받는 조회 화면에는 추가 재료와 소분 조건이 포함되지 않는다.

### 식약처 공개 레시피

[식품의약품안전처 조리식품의 레시피 DB (COOKRCP01)](https://www.foodsafetykorea.go.kr/api/newDatasetDetail.do?svc_no=COOKRCP01)의 메뉴명, 조리 유형, 재료와 분량을 `cookrcp01.json`에 담았다. 동일 이름으로 여러 레시피가 있으면 일련번호로 구분한다. 원본 재료 항목의 첫머리에 인분이 명시된 경우 입력을 채워준다. 원본 인분을 확인한 뒤 원본 분량 전체의 재료비와 직접 작업시간을 입력하면 주문 인분에 맞춰 다시 계산한다. 재료·분량을 확인하고 가격을 낼 근거가 갖춰지면 실험용 오퍼를 만든다. 동일 메뉴 시세가 있으면 시세를 오퍼 기준으로 사용한다.

새 CSV를 받으면 아래 명령으로 레시피 목록을 갱신한 뒤 서울 가격표 HTML을 다시 만든다.

```sh
python3 cookrcp_import.py ~/Downloads/COOKRCP01.csv cookrcp01.json
python3 lookup.py --seoul-workbook ~/Downloads/seoul-menu-prices-cleaned.xlsx local/menu-price-offers.html
```

같은 화면은 `python3 server.py --seoul-workbook ~/Downloads/seoul-menu-prices-cleaned.xlsx`로도 열 수 있다. 브라우저 화면의 세 오퍼는 실험용이다. 서울 모드의 주문 API는 확인된 동일 메뉴 단가를 카탈로그로 사용한다. 작업시간 입력이 필요한 새 레시피는 기준가가 없을 때 재료비와 확인 사유를 반환한다.

## 현재 첫 화면 · 메뉴 가격 조회

메뉴명 하나를 제출하면 카탈로그에 저장된 unit_price를 그대로 표시한다. 예를 들어 새우볶음밥이 11,500원으로 등록되어 있으면 결과는 11,500원이다. 기준가에는 인분 근거를 표시한다. 원본 엑셀을 함께 지정하면 일치하는 메뉴의 매장별 게시 가격과 인분·판매 규격이 함께 나오며, 기준가가 없는 메뉴도 게시 가격을 조회할 수 있다. 띄어쓰기는 무시한다. 아래 명령으로 만든 HTML은 파일을 더블클릭하면 서버 없이 작동한다. 완성 HTML에는 가격 목록이 포함되므로 내부용으로 보관한다.

```sh
python3 lookup.py catalog.json menu-price-lookup.html --workbook gangnam_menu_types.xlsx
```

## 로컬 서버로 같은 화면 실행

별도 제공한 실행 묶음에는 아래의 catalog.json이 들어 있다. Python 3가 설치된 컴퓨터에서 압축을 푼 뒤 해당 폴더에서 실행한다.

```sh
python3 server.py --catalog catalog.json
```

브라우저에서 http://127.0.0.1:8000 을 연다. 게시 가격을 표시하려면 서버 명령에 `--workbook gangnam_menu_types.xlsx`를 추가한다. 원본 엑셀을 읽으려면 openpyxl이 필요하다. Windows에서는 python3 대신 py를 사용할 수 있다. GitHub에서 코드만 받은 경우 다음 명령으로 첨부 가격표에서 catalog.json을 먼저 생성한다.

```sh
python3 -m pip install openpyxl
python3 catalog_import.py gangnam_menu_types.xlsx catalog.json
```

## 명령줄에서 확인

```sh
python3 run_quote.py 새우볶음밥 3 --catalog catalog.json --extra 새우 --extra-grams 100 --containers 3
python3 run_quote.py 새우볶음밥 1
python3 run_quote.py --catalog catalog.json --request-json interpreted.json
python3 -m unittest -v
node --test test_seoul_offers.js
```

카탈로그를 생략한 두 번째 명령은 레시피 가격 계산을 확인하는 방법이다. 요청 해석 JSON은 기존 해석기의 출력을 받는다. 단일 메뉴, 확정된 중량·범위·단가가 있는 기존 고기 증량, R02 간 조절과 R03 기본량 유지부터 지원한다. 미해결 규칙이나 여러 요리가 섞이면 보류한다. 웹 화면은 인분·추가량·용기 수를 직접 입력받는다.

## 가격의 근거

- 강남 카탈로그는 원문과 대표명이 일치하는 일반 단품에서 매장별 가격의 중앙값을 구한 뒤 매장 간 중앙값을 쓴다. 주문 결과에 엑셀 행과 매장 수, 1인분 명시·추정 여부가 남는다. 기준가에는 기본 인건비를 다시 더하지 않는다.
- 레시피 재료비는 `fried_rice.json`과 `recipes.json`의 포장 규격과 소매 표시가를 사용한다. 기존 증량 단가는 `fried_rice.json`에서 가져온다. 시급, 가산율, 용기 단가와 일부 중량 환산은 실험 가정이다. 실제 주문의 요리사 수락가는 별도로 검증해야 한다.
- 로컬 실험 기록은 experiment.sqlite3에 저장한다. requests의 전체 행, seen_at이 있는 행, proceeded_at이 있는 행을 각각 집계한다. 단위는 요청 건수다.
- 개발 초기의 cli.py와 data.json은 가상값 계산 예제로 남아 있다. 현재 웹과 run_quote.py는 이 예제 단가를 사용하지 않는다.

원본 엑셀과 파생 카탈로그, 실험 기록은 공개 저장소에서 제외한다. [개발 로드맵](ROADMAP.md)
