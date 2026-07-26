# TÀI LIỆU 5 — TEAM KICKOFF CHECKLIST V1

**Phạm vi:** Công việc cả nhóm — Ngày 1 và Ngày 2, Tuần 1  
**Cập nhật:** 26/07/2026  
**Mục đích:** Ghi nhận trạng thái có thể xác minh trong repository và các việc cần hoàn tất trên GitHub/máy của từng thành viên.

## 1. Nguyên tắc hoàn thành

Một hạng mục chỉ được đánh dấu hoàn thành khi có bằng chứng tương ứng: repository/setting tồn tại, lệnh chạy được, ảnh chụp cấu hình, hoặc xác nhận của thành viên. Không dùng trạng thái “đã làm gần xong”.

## 2. Ngày 1 — Baseline và repository

| Hạng mục roadmap | Trạng thái | Bằng chứng hoặc hành động còn lại |
|---|---|---|
| Đọc Project Charter, PRD, Gameplay Rules, Roadmap, Decision Log | Cần xác nhận đội | Tài liệu nguồn nằm trong `docs/`. Mỗi A/B/C xác nhận đã đọc và ghi câu hỏi/ý kiến trước khi code. |
| GitHub repository | Đã có | Remote `origin` đang trỏ tới `https://github.com/DoMinh27/Codehehe`; nhánh làm việc là `main`, theo dõi `origin/main`. |
| GitHub Project | Chưa xác minh | Tạo một Project cho repository và dùng các cột ở mục 4. Cần quyền GitHub của chủ repository. |
| Mời ba thành viên | Chưa xác minh | Chủ repository mời A, B, C với quyền phù hợp; thành viên phải chấp nhận lời mời. |
| Branch protection cho `main` | Chưa xác minh | Bật pull request bắt buộc, tối thiểu một review, không cho push trực tiếp; yêu cầu status check khi test đã được tạo. |
| Quy ước task/PR | Sẵn sàng áp dụng | Mỗi task có một owner, acceptance criteria và một PR có reviewer theo Charter/Decision Log. |

### Acceptance criteria cho repository

* `main` là nhánh mặc định và luôn có thể chạy sau khi môi trường được thiết lập.
* Không thành viên nào push trực tiếp vào `main`.
* PR cần ít nhất một reviewer trước merge.
* Issue/Project item luôn có owner, trạng thái và acceptance criteria.

## 3. Ngày 2 — Environment và technical baseline

| Hạng mục roadmap | Trạng thái | Bằng chứng hoặc hành động còn lại |
|---|---|---|
| Git | Đã xác minh | Máy hiện tại có Git `2.55.0.windows.3`. |
| Python 3.12 | Blocked trên máy hiện tại | `python` và `py` không chạy; các đường dẫn Python 3.12 thông dụng cũng không tồn tại. Cài Python 3.12 x64 từ nguồn chính thức, bật launcher/PATH, rồi chạy lại checklist ở mục 5. |
| VS Code và extensions | Cần xác nhận từng máy | Cài VS Code cùng Python, Ruff, GitLens và SQLite Viewer extension theo roadmap. Không commit cấu hình người dùng vào repo. |
| Clone repository | Đã có workspace | Workspace hiện tại là checkout của repository và có remote `origin`. A/B/C vẫn cần tự clone về máy của mình. |
| `.venv` | Blocked bởi Python | Chỉ tạo sau khi `py -3.12` hoặc Python 3.12 chạy được. Không commit `.venv/`. |
| `requirements.txt` | Đã có, đã kiểm tra | Pin Django 5.2.16, python-dotenv, Ruff và dependency Django liên quan. |
| `.env.example` | Đã có, đã kiểm tra | Bao gồm `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `JUDGE0_BASE_URL`, `JUDGE0_API_KEY`; không có secret thật. |
| `.gitignore` | Đã cập nhật | Bỏ qua `.venv/`, `.env`, cache Python/Ruff, coverage, SQLite DB và generated static/media files. |

## 4. GitHub Project board chuẩn

Tạo đúng các cột sau, theo thứ tự:

```text
Backlog → Ready → In Progress → Review → Testing → Done
                         └────────────→ Blocked
```

Mỗi card tối thiểu cần có:

* Tiêu đề theo outcome, không chỉ tên file.
* Một owner chính: A, B hoặc C.
* Acceptance criteria có thể test/demo.
* Liên kết branch/PR khi bắt đầu code.
* Nhãn `blocked` và mô tả blocker khi không thể tiếp tục.

## 5. Lệnh xác minh sau khi cài Python 3.12

Chạy tại thư mục repository `Code` trên từng máy:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m django --version
ruff --version
```

Kết quả chấp nhận:

* Lệnh đầu trả về Python `3.12.x`.
* `.venv` được tạo cục bộ và bị Git bỏ qua.
* Django trả về `5.2.16`.
* Ruff chạy được trong virtual environment.
* Không có `.env` chứa secret bị stage vào Git.

## 6. Việc tiếp theo theo owner

| Owner | Việc cần làm ngay |
|---|---|
| Chủ repository | Tạo GitHub Project, mời A/B/C, bật branch protection cho `main`. |
| A/B/C | Cài Python 3.12, clone repo, tạo `.venv`, cài requirements và báo lại kết quả lệnh xác minh. |
| B | Sau khi A chốt route/context, bắt đầu `base.html` và cấu trúc static ở Ngày 3. |

