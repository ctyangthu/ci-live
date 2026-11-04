# 中華航空航班動態系統

依中華航空 2026/27 冬季電子班表（2026/10/25–2027/3/27），在世界地圖上推算每一個航班的位置，並提供桃園、松山、清泉崗、高雄的出發／抵達看板、時刻表、航線網路與資料查核。

網址：https://ctyangthu.github.io/ci-live/

以 2026/11/2–11/8 這一週為例，自臺灣出發 591 班自營航班（華航 569、華信 22），加上他航共掛 200 班。自營航班全季飛往 59 個國際航點：

| 機場 | 華航自營 | 華信自營 | 他航共掛 | 自營航點 |
|---|---:|---:|---:|---|
| 桃園 TPE | 461 | 7 | 148 | 50 個（華信：廈門） |
| 松山 TSA | 23 | 5 | 30 | 羽田、虹橋、金浦（華信：福州、武漢） |
| 清泉崗 RMQ | 7 | 7 | 0 | 沖繩（華信：胡志明市） |
| 高雄 KHH | 78 | 3 | 22 | 14 個（華信：廈門） |

## 功能

- **三類航班可切換**：華航自營、華信自營（預設顯示）、他航共掛（預設隱藏）。官方時刻表三類都有，而清泉崗—胡志明市、松山—福州／武漢、桃園與高雄—廈門只有華信飛，所以華信算在內。查詢共掛班號（如 CI9220）會自動打開共掛。
- **依日期套用班表**：每行記錄行駛星期與期間，各機場時區與日光節約時間由瀏覽器換算。富山加班機、札幌 CI2130（12/16 起）、重慶（11/18 起）、法蘭克福取消日都依日期判斷。
- **即時與模擬**：預設使用現在時間；可切換日期、拖曳時間軸（臺北時間），並以 1×–3600× 播放。前一兩天起飛、仍在空中的長程航班會繼續顯示。
- **地圖**：Miller 投影、以東經 143° 為中心。航線依大圓繪製並以區域上色，飛機沿航線移動；陰影為當下的夜間區域，虛線與空心飛機是共掛。
- **航班詳情**：起降時間（當地與臺北時間）、飛行進度、推算地速與高度、執飛公司、機型、當週班期。CI53／CI54 經停布里斯本，依日期判斷是否續飛奧克蘭。
- **看板、空中、時刻表、航點**：看板可依四座機場篩選；時刻表可看所選日期、當週或整季，並標示「表外」航班。
- **查核**：四座機場的航點與班次、與機場資料的比對結果、官方時刻表未列的航班、來源清單。

## 查核結果（2026/11/4）

與七份機場公布資料（共 1,454 筆航班）比對，**沒有一班未收錄**。高雄四週班表（759 筆）與松山週表（116 筆）連時刻都一致。AeroLOPA（OAG）列出的 96 個華航班號也都有。

只看官方時刻表（Issue 1）會漏掉這些，已補入並標示「表外」：

| 航班 | 航段 | 日期 | 來源 |
|---|---|---|---|
| CI2164／CI2165 | 高雄—仁川 | 12/6、12/3 | TDX |
| CI7528／CI7529 | 桃園—庄內 | 11/3–11/19 間 4–5 班 | TDX、桃園機場 |
| CI7923 | 桃園—新加坡 | 11/6 | TDX |
| CI7927／7928／7929 | 高雄—新加坡 | 11/6–11/13 間 4 班 | 高雄機場 |
| CI9802／CI9803 | 桃園—馬尼拉（菲航共掛） | 2/4–2/11 間 4 班 | TDX |
| CI9503／CI9504 | 桃園—汶萊（汶萊航空共掛）週五班 | 11/6–3/26 | TDX |
| CI9958／CI9959 | 桃園—成田（日航共掛）加班日 | 2/2–3/7 | TDX |

查過但本季沒有：清泉崗—北九州、高雄—高松（維基百科列為部分包機）、桃園—重慶 CI553/554（據 AeroRoutes 延到 2027/3/31 之後）。完整清單在頁面的查核分頁。

## 限制

- 航班狀態與位置依表定時間推算（扣除約 14 分鐘滑行出發、6 分鐘滑行抵達，沿大圓航線移動），不含延誤、取消、改降等即時資訊；實際航路會因空域與風向繞行，兩岸航線尤其明顯。
- 桃園看板只涵蓋前一天到後一天，這次查核涵蓋 11/3–11/5（週二到週四），其他星期靠 TDX 與 AeroLOPA 檢查。`audit_airports.py` 宜在不同星期各跑一次。
- TDX 的高雄、松山、清泉崗資料只到 2027/1/3，之後的日期沿用官方時刻表，並套用 TDX 同星期的時刻。
- 三處是判斷而非原始資料：官方時刻表的 CI2063 印成 3/8（週一），與它的飛行日欄（二、六）和回程日期不符，推定為 3/9；TDX 把 CI54 布里斯本的起飛時間填成抵達時間 21:25，這裡沿用官方的 23:10；官方時刻表有、TDX 當日未排的航班（如 CI851 11/24）視為當日不飛。
- 機型依官方時刻表；標 EQV 的華航航班改用桃園機場與 AeroLOPA 見到的機型（`data/aircraft-eqv.txt`），只有 TDX 才有的航班多半不知機型。
- 超出 2026/10/25–2027/3/27 沒有班表可推算，頁面會提示。
- 本系統為非官方展示，與中華航空無關，實際航班請以中華航空公告為準。

## 專案結構

```
src/app.html                網頁原始碼（資料以佔位字串嵌入）
data/timetable-pdf.json     官方電子班表解析結果（只留臺灣相關航段）
data/tdx-snapshot.json      TDX 國際定期航班快照
data/extra-flights.txt      只見於機場資料的航班（手動維護）
data/aircraft-eqv.txt       官方標 EQV 的航班實際機型（手動維護）
data/schedule-nw26.txt      合併後的班表：每行一個航段（由 build_schedule.py 產生）
data/airports.json          機場：中英文名稱、區域、座標、IANA 時區
data/map.json               投影並簡化後的陸地、國界與臺灣路徑
data/audit-sources.json     官方時刻表與 TDX 的差異（由 build_schedule.py 產生）
data/audit-airports.json    與機場資料的比對結果（由 audit_airports.py 產生）
data/audit-notes.json       查核分頁的說明文字與來源（手動維護）
tools/parse_timetable.py    解析官方 PDF（需要 pypdf）
tools/fetch_tdx.py          下載 TDX 班表
tools/build_schedule.py     合併官方時刻表與 TDX，產生班表與差異清單
tools/schedule.py           解析 schedule-nw26.txt
tools/check_schedule.py     以時區換算飛行時間，檢查 +1/+2 與時刻是否合理
tools/audit_airports.py     與四座機場公布的航班比對
tools/build_map.py          由 Natural Earth 1:50m（world-atlas）產生 data/map.json
tools/build.py              組出 dist/index.html
```

## 建置

```bash
python3 tools/build.py
```

產出的 `dist/index.html` 可直接用瀏覽器開啟。推送到 `main` 後，GitHub Actions 會自動建置並部署到 GitHub Pages。

更新班表時，依序執行（PDF 從[華航時刻表頁面](https://www.china-airlines.com/tw/zh/fly/flight-status/timetable)的「電子班表」下載；TDX 未帶金鑰每天只能查幾次，用完會回 401，可設定 `TDX_TOKEN`）：

```bash
python3 tools/parse_timetable.py CI-timetable.pdf
```

```bash
python3 tools/fetch_tdx.py
```

```bash
python3 tools/build_schedule.py
```

```bash
python3 tools/check_schedule.py
```

```bash
python3 tools/audit_airports.py
```

```bash
python3 tools/build.py
```

## 資料來源

- [中華航空電子班表](https://www.china-airlines.com/tw/zh/fly/flight-status/timetable)（Issue 1，2026/10/25–2027/3/27，檔案日期 2026/10/20）：班表主幹。
- [TDX 運輸資料流通服務](https://tdx.transportdata.tw/) 國際定期航班（2026/11/4 抓取）：時刻以此為準。
- 機場官方資料：[桃園機場](https://www.taoyuan-airport.com/)即時航班（2026/11/3–11/5）、[松山機場定期班表](https://www.tsa.gov.tw/flights/international/regular)、[清泉崗機場航班時刻表](https://www.tca.gov.tw/?act=fids&code=regular_flight)、[高雄機場定期班表](https://www.kia.gov.tw/FLIPLAN.html)（2026/11/2–11/29）。
- 交叉檢查：[AeroLOPA](https://www.aerolopa.com/ci)（OAG，2026/11/3–12/2）、[AeroRoutes](https://www.aeroroutes.com/eng/tag/China+Airlines) 華航 2026/27 冬季公告、[維基百科中華航空航點](https://zh.wikipedia.org/zh-tw/%E4%B8%AD%E5%8D%8E%E8%88%AA%E7%A9%BA%E8%88%AA%E7%82%B9)（只用來找可能遺漏的航點）。
- 地圖：[world-atlas](https://github.com/topojson/world-atlas)（Natural Earth 1:50m，公有領域）。
