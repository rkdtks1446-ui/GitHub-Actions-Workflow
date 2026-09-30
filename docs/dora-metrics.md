# DORA 지표 수집 안내

## 자동 수집

`.github/workflows/dora-metrics.yml`은 매일 UTC 02:17, 매주 월요일 UTC 03:17, production 배포 성공 이벤트, 또는 수동 실행 시 최근 90일 데이터를 모아 `data/dora-metrics.json`을 갱신합니다. 실행마다 JSON을 `dora-metrics-json-<run number>` artifact로 90일간 보관합니다. 별도 PAT나 외부 데이터베이스 없이 저장소의 `GITHUB_TOKEN`을 사용합니다. 저장소 설정에서 Actions의 읽기/쓰기 권한이 허용되어야 결과 커밋이 올라갑니다.

매주 월요일 workflow는 직전 월요일부터 일요일까지의 완전한 주간 지표를 `reports/weekly/YYYY-MM-DD.md`로 생성하고, `reports/weekly/latest.md`도 갱신합니다. 주간 보고서는 저장소에 커밋되며 `dora-weekly-report-<run number>` artifact로 365일 보관합니다.

수집 스크립트는 GitHub REST API의 성공한 `production` 배포, 병합 PR 및 PR 커밋, `incident` 라벨 이슈를 사용합니다. Lead time은 PR의 가장 이른 커밋부터 그 커밋을 포함하는 첫 성공 production 배포까지 계산합니다. `change-failure` 라벨이 있는 배포 PR을 실패 변경으로 분류합니다.

## 저장소에서 필요한 규칙

- 실제 배포 job은 GitHub Actions의 `environment: production`을 선언해야 합니다.
- 장애 이슈에는 `incident` 라벨을 달고, 복구가 확인되면 이슈를 닫습니다.
- 장애를 유발한 배포 변경 PR에는 병합 전에 `change-failure` 라벨을 붙입니다.
- 배포 커밋은 해당 변경 PR의 merge commit을 포함해야 연결할 수 있습니다.

이 저장소는 아직 앱 배포 job이 없으므로 성공 배포가 등록되기 전까지 네 지표를 `—`로 표시합니다. workflow가 배포 기록을 자동으로 만들어 주는 것은 아닙니다.

## 해석 시 주의

- Change Failure Rate는 운영 장애가 났던 배포 PR에 라벨을 붙이는 팀 프로세스에 의존합니다. 라벨 누락은 비율을 낮게 보이게 할 수 있습니다.
- MTTR은 `incident` 이슈의 생성부터 종료까지의 시간이며, 이슈 작성 지연과 종료 시점의 영향을 받습니다.
- Lead time은 PR 첫 커밋 기준입니다. squash/rebase 및 커밋 날짜 보정 정책에 따라 실제 작성 시점과 차이가 날 수 있습니다.
- 결과는 저장소 단위 최근 90일 집계이며, DORA 등급을 임의로 판정하지 않습니다.

## 로컬 확인

```powershell
python -m unittest discover -s tests -v
python -m http.server 8001
```

대시보드는 `http://localhost:8001/dashboard/`에서 확인할 수 있습니다.