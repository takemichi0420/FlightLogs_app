# ArduPilot Flight Record App

ArduPilot ログから飛行記録ドラフトを作成し、正式値の入力、確定、PDF出力まで行う Django + React の MVP です。

## 構成

- `backend/`
  - Django 5.2 + Django REST Framework
- `frontend/`
  - Vite + React + TypeScript + Tailwind CSS
- `venv/`
  - プロジェクト用 Python 仮想環境

## セットアップ

### 1. Python 仮想環境

この環境では `ensurepip` がないため、仮想環境は `--without-pip` で作成し、外側の `pip` から注入しています。

```bash
cd /home/ardupilot/GitHub/workshop/FightLog_app_project
python3 -m venv --without-pip venv
python3 -m pip --python venv/bin/python install --upgrade pip setuptools wheel
python3 -m pip --python venv/bin/python install -r backend/requirements.txt
```

### 2. Node modules

```bash
cd /home/ardupilot/GitHub/workshop/FightLog_app_project/frontend
npm install
```

## 起動

### Backend

```bash
cd /home/ardupilot/GitHub/workshop/FightLog_app_project/backend
../venv/bin/python manage.py migrate
../venv/bin/python manage.py runserver
```

### Frontend

```bash
cd /home/ardupilot/GitHub/workshop/FightLog_app_project/frontend
npm run dev
```

フロントエンドは `http://127.0.0.1:5173`、バックエンドは `http://127.0.0.1:8000` を想定しています。

## 利用手順

1. ログイン画面でアカウントを新規作成する。
2. `Aircraft` で機体を登録する。
3. `Pilots` で操縦者を登録する。
4. `飛行記録` で `.bin` / `.log` をアップロードする。MAVLink接続が使える場合は、`MAVLinkから取り込み` で機体内ログを直接取得できる。
5. 解析完了後、対象レコードを開いて正式値を入力する。
6. `確定` を押す。
7. `PDFダウンロード` で PDF を取得する。

## MAVLinkからの直接取込み

`飛行記録` 画面の `MAVLinkから取り込み` で、ArduPilot/SITL のログ一覧を取得し、選択したログを `.bin` として保存して既存の解析ジョブへ渡します。

### 画面操作

1. ArduPilot/SITL または機体をMAVLink接続可能な状態にする。
2. `接続先` にMAVLink接続文字列を入力する。
   - SITL例: `udp:127.0.0.1:14550`
   - TCP例: `tcp:127.0.0.1:5760`
   - シリアル例: `/dev/ttyUSB0`
3. シリアル接続の場合は `ボーレート` を設定する。UDP/TCPでは通常そのままでよい。
4. 必要に応じて `機体` と `操縦者` を選択する。
5. `ログ一覧を取得` を押す。
6. 取り込むログを選択し、`選択ログを取り込んで解析` を押す。

ログ一覧を取得せずに `最新ログを取り込んで解析` を押すと、バックエンドがログ一覧を取得して最新ログを選択します。

### API

- `POST /api/mavlink/logs/`
  - 入力: `connection`, `baud`, `timeout_s`
  - 出力: `logs`
- `POST /api/mavlink/import-log/`
  - 入力: `connection`, `baud`, `timeout_s`, `log_id`, `aircraft_id`, `pilot_id`
  - 出力: 既存の `AnalysisJob`

取り込んだログは `FlightRecord.source_file` に `.bin` として保存され、既存の `parse_log_file()` と `AnalysisJob` で解析されます。

## 検証コマンド

```bash
cd /home/ardupilot/GitHub/workshop/FightLog_app_project/backend
../venv/bin/python manage.py check
../venv/bin/python manage.py test
../venv/bin/ruff check .

cd /home/ardupilot/GitHub/workshop/FightLog_app_project/frontend
npm run build
```

## MVP上の制約

- 正式対応ログは `.bin` と `.log` のみです。
- 気象参考値は未接続時に `reference_unavailable` として保存されます。
- 逆ジオコーディングは `REVERSE_GEOCODE_URL` を設定しない場合、緯度経度ベースのフォールバック文字列を返します。
- ログ解析ジョブは軽量なスレッド実行であり、本番向けジョブキューではありません。
- MAVLink取込みはリクエスト内でログダウンロードを行います。大きなログや不安定な通信では時間がかかるため、本番運用ではバックグラウンドジョブ化を推奨します。

## 環境変数

主な設定値は以下です。

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `REVERSE_GEOCODE_URL`
- `MAVLINK_LOG_MAX_BYTES`
# FlightLogs_app
