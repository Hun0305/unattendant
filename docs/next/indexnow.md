# IndexNow

# 일단 글을 많이 써야 인덱싱하고 말고..

새 글이나 고친 글의 주소를 검색엔진에 바로 알려 색인을 앞당긴다. Google은 IndexNow를 지원하지 않으므로 Search Console 사이트맵으로 받는다.

- **지금 상태 (2026-10-07)**: 뒤로 미뤘다. 키 파일이 없어서 `request_indexing`은 "키가 없다"고 알리고 건너뛴다 (`agent/blogops/server.py`).
- **켜는 시점**: 첫 소개글을 발행할 때 키 파일을 배포하고, 그 글로 처음 요청한다.
- 구현은 `agent/blogops/indexnow.py`에 있다. 발행 흐름에서 언제 부르는지는 [blogops.md](../blogops.md) 1절과 5절에 있다.

## 동작 방식

1. 사이트 루트에 `<키>.txt` 파일을 둔다. 내용도 키다.
2. `https://api.indexnow.org/indexnow`로 주소 목록과 키를 POST한다.
3. 검색엔진이 `https://unattendant.dev/<키>.txt`를 가져와 키가 맞는지 확인한다. 맞으면 우리 사이트가 보낸 요청으로 인정한다.
4. api.indexnow.org에 보낸 주소는 참여하는 검색엔진 모두에 공유된다. Bing, 네이버, Yandex, Seznam, Yep 등이 참여한다 ([목록](https://www.indexnow.org/searchengines.json)). 엔진마다 따로 보낼 필요가 없다.

blogops가 보내는 요청은 다음과 같다.

```json
POST https://api.indexnow.org/indexnow
Content-Type: application/json; charset=utf-8

{
  "host": "unattendant.dev",
  "key": "<키>",
  "keyLocation": "https://unattendant.dev/<키>.txt",
  "urlList": ["https://unattendant.dev/posts/<슬러그>/"]
}
```

## 키 파일

- 위치는 `site/static/<키>.txt`다. Hugo가 사이트 루트로 그대로 복사한다.
- 키는 소문자 16진수 32자다. 프로토콜은 8~128자의 영문, 숫자, `-`를 허용하지만, blogops는 이 형식만 키로 인식한다 (`KEY_RE`).
- **비밀값이 아니다.** IndexNow가 공개를 요구하는 파일이다. `.env`에 넣지 않고 사이트 레포에 커밋한다. 키를 남이 알아도 보낼 수 있는 건 우리 사이트 주소의 색인 요청뿐이다.
- gitleaks에는 걸리지 않는다. 2026-10-07에 샘플 키 파일로 `gitleaks dir --config ops/gitleaks.toml`을 돌려 `no leaks found`를 확인했다.
- 키 파일은 하나만 둔다. 여러 개 있으면 blogops는 이름순으로 첫 번째를 쓴다.
- 파일 주인은 사람이다. 사이트 레포에서 `content/posts/` 밖은 사람 몫이다 ([blogops.md](../blogops.md) 7절).

## 켜는 방법

작업실(`~/unattendant`)에서 한다.

**1. 키 만들기**

```bash
cd ~/unattendant/agent
python3 -c "from blogops.config import Config; from blogops import indexnow; print(indexnow.create_key(Config.from_env()))"
```

`site/static/<키>.txt`가 생기고 키가 출력된다. 키 파일이 이미 있으면 새로 만들지 않고 그 키를 그대로 돌려준다.

**2. 사이트 레포에 커밋하고 push**

```bash
cd ~/unattendant/site
git add static/<키>.txt
git commit   # chore(site): IndexNow 키 파일 추가
git push
```

**3. 배포하고 확인**

사이트를 다시 빌드하고 키 파일이 열리는지 확인한다.

```bash
cd ~/unattendant/site && hugo --gc --minify --cleanDestinationDir
curl -s https://unattendant.dev/<키>.txt   # 키가 그대로 나와야 한다
```

- 작업실과 매장을 나누기 전에는 작업실에서 빌드한 결과가 바로 공개된다. 커밋하지 않은 템플릿 작업이 있으면 같이 나가니, 빌드하기 전에 `git status`를 본다.
- 나눈 뒤에는 Huninn이 사이클을 시작할 때 pull하고 다시 빌드한다 ([blogops.md](../blogops.md) 7절).

**4. 첫 요청 (첫 소개글)**

소개글을 발행한 뒤 그 주소로 요청한다.

```bash
cd ~/unattendant/agent
python3 -c "from blogops.config import Config; from blogops import indexnow; print(indexnow.request_indexing(Config.from_env(), ['https://unattendant.dev/posts/starting-unattendant/']))"
```

`{'status': 200, ...}`이나 `202`가 나오면 성공이다. 첫 요청은 키를 아직 확인하는 중이라 202가 나올 수 있다. 요청은 `logs/`에 `request_indexing`으로 기록된다.

**5. 결과 확인**

- Bing Webmaster Tools의 IndexNow 메뉴에서 제출된 주소를 본다.
- 며칠 뒤 Bing과 네이버에서 `site:unattendant.dev`로 검색해 본다.

**6. 기록**

[todo.md](../todo.md)의 "IndexNow 실제 사용"을 체크한다. 이후로는 Huninn이 `publish_post` 다음에 `request_indexing`을 부르고, 따로 할 일은 없다.

## 응답 코드

| 코드 | 뜻 | 할 일 |
| --- | --- | --- |
| 200 | 접수됨 | 없음 |
| 202 | 접수됨, 키 확인 중 | 없음. 첫 요청에서 흔하다 |
| 400 | 요청 형식이 잘못됨 | blogops 코드 확인 |
| 403 | 키가 맞지 않음 | `https://unattendant.dev/<키>.txt`가 열리는지, 내용이 키와 같은지 확인 |
| 422 | 주소가 host와 맞지 않거나 키 형식이 다름 | 다른 도메인 주소가 섞였는지 확인 |
| 429 | 너무 자주 보내서 스팸으로 의심받음 | 같은 주소를 반복해서 보내지 않았는지 확인 |

blogops는 200과 202가 아닌 응답을 모두 에러로 돌려준다. 이렇게 실패해도 발행 자체는 이미 끝난 상태다. 색인 요청만 다음 사이클에서 다시 하면 된다.

## 운영 규칙

- **바뀐 주소만 보낸다.** 새로 발행한 글이나 내용을 고친 글만 보내고, 같은 주소를 이유 없이 다시 보내지 않는다.
- 한 번에 보낼 수 있는 주소는 100개까지다. blogops가 정한 한도이고, 프로토콜의 한도는 10,000개다.
- 우리 사이트(`hugo.toml`의 `baseURL`)가 아닌 주소가 섞이면 요청을 보내기 전에 거부한다.
- **키를 바꿀 때**는 새 키 파일을 배포한 다음에 이전 파일을 지운다. 지우는 사이에 요청이 오면 403이 난다.

## 참고

- [IndexNow 문서](https://www.indexnow.org/documentation)
- [GeekNews: 네이버 서치어드바이저 IndexNow 지원](https://news.hada.io/topic?id=19225)
