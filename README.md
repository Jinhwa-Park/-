# 레시피 가격 측정기

요리와 인분을 입력해 강남 음식점의 게시 가격에 기반한 실험용 오퍼를 계산한다. 기준표에 없는 새우볶음밥은 레시피와 구매 규격이 확인된 상품의 사용량으로 계산한다. 그 밖의 미지원 요리는 확인이 필요한 이유를 반환한다. 주문 시 외부 API 호출은 없다.

## 현재 첫 화면 · 메뉴 가격 조회

메뉴명 하나를 제출하면 카탈로그에 저장된 unit_price를 그대로 표시한다. 예를 들어 새우볶음밥이 11,500원으로 등록되어 있으면 결과는 11,500원이다. 띄어쓰기는 무시하며 미등록 메뉴는 조회 실패로 표시한다. 아래 명령으로 만든 HTML은 파일을 더블클릭하면 서버 없이 작동한다. 완성 HTML에는 가격 목록이 포함되므로 내부용으로 보관한다.

```sh
python3 lookup.py catalog.json menu-price-lookup.html
```

## 로컬 서버로 같은 화면 실행

별도 제공한 실행 묶음에는 아래의 catalog.json이 들어 있다. Python 3가 설치된 컴퓨터에서 압축을 푼 뒤 해당 폴더에서 실행한다.

```sh
python3 server.py --catalog catalog.json
```

브라우저에서 http://127.0.0.1:8000 을 연다. Windows에서는 python3 대신 py를 사용할 수 있다. GitHub에서 코드만 받은 경우 다음 명령으로 첨부 가격표에서 catalog.json을 먼저 생성한다.

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
```

카탈로그를 생략한 두 번째 명령은 레시피 가격 계산을 확인하는 방법이다. 요청 해석 JSON은 기존 해석기의 출력을 받는다. 단일 메뉴, 확정된 중량·범위·단가가 있는 기존 고기 증량, R02 간 조절과 R03 기본량 유지부터 지원한다. 미해결 규칙이나 여러 요리가 섞이면 보류한다. 웹 화면은 인분·추가량·용기 수를 직접 입력받는다.

## 가격의 근거

- 강남 카탈로그는 원문과 대표명이 일치하는 일반 단품에서 매장별 가격의 중앙값을 구한 뒤 매장 간 중앙값을 쓴다. 주문 결과에 엑셀 행과 매장 수, 1인분 명시·추정 여부가 남는다. 기준가에는 기본 인건비를 다시 더하지 않는다.
- 볶음밥 재료비와 증량 단가는 fried_rice.json의 상품 규격·기록 가격을 사용한다. 시간, 시급, 가산율, 용기 단가와 일부 중량 환산은 실험 가정이다. 최종 금액은 요리사가 수락한 가격으로 검증되지 않았다.
- 로컬 실험 기록은 experiment.sqlite3에 저장한다. requests의 전체 행, seen_at이 있는 행, proceeded_at이 있는 행을 각각 집계한다. 단위는 요청 건수다.
- 개발 초기의 cli.py와 data.json은 가상값 계산 예제로 남아 있다. 현재 웹과 run_quote.py는 이 예제 단가를 사용하지 않는다.

원본 엑셀과 파생 카탈로그, 실험 기록은 공개 저장소에서 제외한다. [개발 로드맵](ROADMAP.md)
