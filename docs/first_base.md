# CODEHEHE — MASTER PROJECT BASELINE

**Loại tài liệu:** Project Charter + Product Context + PRD Baseline + Technical Baseline + Delivery Roadmap
**Trạng thái:** Tài liệu nguồn sự thật chính thức của dự án
**Dự án:** CodeHehe
**Cuộc thi:** SOFTCON cấp trường
**Đội ngũ:** 3 sinh viên năm hai chuyên ngành Trí tuệ nhân tạo
**Thời gian triển khai V1:** Khoảng 4 tuần
**Ngày áp dụng:** Từ thời điểm tài liệu này được chấp thuận
**Phạm vi:** Từ chuẩn bị môi trường, phát triển, kiểm thử, triển khai đến demo và bảo vệ trước hội đồng

---

# 1. Mục đích của tài liệu

Tài liệu này hợp nhất toàn bộ quyết định đã được đưa ra trong quá trình thảo luận dự án CodeHehe.

Tài liệu được sử dụng để:

* Giúp cả ba thành viên hiểu cùng một phiên bản của dự án.
* Làm căn cứ viết System Design, Database Design và Product Backlog.
* Giới hạn phạm vi mà Codex được phép triển khai.
* Giải quyết các tranh luận về tính năng, công nghệ và thứ tự làm việc.
* Làm nguồn tham chiếu cho phát triển, kiểm thử, triển khai và thuyết trình.
* Giúp người mới đọc có thể hiểu dự án mà không cần xem lại cuộc trò chuyện gốc.
* Phân biệt rõ quyết định đang có hiệu lực với các phương án cũ đã bị thay thế.
* Giữ định hướng Energy, Skills và game hóa trong khi đơn giản hóa V1.

Nếu nội dung trong prompt Codex, task, pull request, tài liệu cũ hoặc trao đổi miệng mâu thuẫn với tài liệu này, tài liệu này được ưu tiên, trừ khi có một Change Request mới được cả nhóm chấp thuận và ghi vào Decision Log.

---

# 2. Quy tắc ưu tiên quyết định

Khi có mâu thuẫn giữa các quyết định trong lịch sử dự án, sử dụng thứ tự ưu tiên sau:

1. Quyết định cuối cùng được ghi rõ là “chốt”, “baseline” hoặc “áp dụng chính thức”.
2. PRD V1 và Gameplay Specification đã được nhóm phê duyệt.
3. Tài liệu Master Project Baseline này.
4. System Design và Database Design sau khi được chốt.
5. Các ví dụ, đề xuất hoặc phương án nghiên cứu trước đó.

Các nội dung từng được đề xuất nhưng sau đó bị thay thế vẫn được ghi lại trong phần “Lịch sử quyết định và phương án đã loại bỏ”, nhưng không còn là kiến trúc triển khai V1.

---

# 3. Thông tin tổng quan

## 3.1. Tên dự án

**Tên chính thức:** CodeHehe

Tên “Code Arena” từng được sử dụng trong một số tài liệu nháp. Tất cả tài liệu chính thức phải đổi sang CodeHehe để tránh không thống nhất thương hiệu.

## 3.2. Loại sản phẩm

CodeHehe là nền tảng học và thi đấu lập trình 1v1 có yếu tố game hóa.

## 3.3. Bối cảnh

* Sản phẩm được xây dựng để tham gia cuộc thi SOFTCON cấp trường.
* Nhóm cần tạo sản phẩm chạy được.
* Nhóm cần thuyết trình được.
* Nhóm dự kiến public source code.
* Sản phẩm không được đánh giá như một startup cần phục vụ quy mô lớn ngay từ V1.
* Mục tiêu chính là chứng minh ý tưởng, gameplay và năng lực triển khai của nhóm.

## 3.4. Đội ngũ

Nhóm có ba thành viên:

* Đều là sinh viên năm hai ngành Trí tuệ nhân tạo.
* Có kiến thức Python.
* Có kiến thức Machine Learning và Deep Learning cơ bản.
* Biết HTML, CSS và JavaScript ở mức cơ bản.
* Chưa có kinh nghiệm đáng kể về:

  * Thiết kế database.
  * Backend web.
  * Frontend architecture.
  * Kết nối frontend với backend.
  * Realtime system.
  * Cloud deployment.
  * Distributed system.
  * Database transaction và concurrency.
  * DevOps production.

## 3.5. Công cụ hỗ trợ

Nhóm sử dụng Codex để hỗ trợ viết code.

Codex có thể làm phần lớn công việc triển khai kỹ thuật, nhưng:

* Codex không được tự quyết định sản phẩm.
* Codex không được tự đổi kiến trúc.
* Codex không được tự thêm công nghệ.
* Codex không được tự thêm model ngoài thiết kế.
* Codex không được tự sửa gameplay.
* Nhóm phải hiểu được code trước khi merge.
* Không được để sản phẩm trở thành hệ thống chỉ Codex hiểu.
* Khi bảo vệ trước hội đồng, cả ba thành viên phải giải thích được các flow chính.

## 3.6. Tài nguyên cloud

Nhóm đã đăng ký **Azure for Students** và có:

* 100 USD credit.
* Thời hạn credit khoảng 12 tháng.

Quyết định:

* Không dùng Azure ngay từ ngày đầu.
* Không học cloud song song với toàn bộ Django, database và Judge0 trong giai đoạn đầu.
* Hai tuần đầu ưu tiên phát triển local.
* Chỉ bắt đầu triển khai Azure khi ít nhất Submission Vertical Slice đã hoạt động.
* Tốt nhất bắt đầu triển khai bản skeleton sau khi Create Room và Join Room đã hoạt động.
* Credit được ưu tiên cho:

  * Máy chủ demo.
  * Judge0 nếu cần self-host.
  * Thử nghiệm deployment.
* Không sử dụng Kubernetes, Service Bus, Azure Redis, Functions hoặc kiến trúc cloud phức tạp trong V1.

---

# 4. Vấn đề sản phẩm

Các nền tảng luyện lập trình phổ biến như LeetCode, HackerRank hoặc Codeforces chủ yếu tập trung vào:

* Giải bài cá nhân.
* Thi đấu thuật toán truyền thống.
* Bảng xếp hạng và kết quả.
* Ít cơ chế tương tác chiến thuật trực tiếp trong lúc giải bài.

Với người mới học Python, trải nghiệm này có thể:

* Thiếu tương tác trực tiếp.
* Thiếu yếu tố trò chơi.
* Khó duy trì động lực.
* Tạo cảm giác luyện bài đơn điệu.
* Không tạo cảm giác đang tham gia một trận đấu.
* Chưa tận dụng được cơ chế thưởng, tài nguyên và kỹ năng để tạo nhịp chơi.

CodeHehe hướng tới việc biến hoạt động giải bài lập trình thành một trận đấu có nhịp độ, cạnh tranh và chiến thuật.

---

# 5. Giải pháp sản phẩm

CodeHehe là nền tảng coding battle 1v1.

Trong một trận đấu cơ bản:

1. Hai người chơi vào cùng một phòng.
2. Hệ thống cố định một danh sách bài chung cho trận.
3. Cả hai nhận cùng danh sách bài.
4. Mỗi người giải bài theo tiến trình độc lập.
5. Người chơi viết và submit code Python.
6. Hệ thống sử dụng hidden tests để chấm bài.
7. Người chơi nhận điểm khi Accepted.
8. Người Accepted bài trước có thể nhận First-solve bonus.
9. Hai người theo dõi điểm và tiến độ của đối thủ gần thời gian thực.
10. Trận kết thúc theo timer phía server.
11. Hệ thống xác định thắng, thua hoặc hòa.

Trong các phiên bản tiếp theo:

* Giải bài tạo Energy.
* Energy được dùng cho Hint hoặc Skills.
* Skills tạo tác động chiến thuật lên đối thủ.
* Người chơi có cơ chế phòng thủ.
* Một số hiệu ứng kích hoạt minigame.
* Elo và Rank tạo hệ thống cạnh tranh dài hạn.

---

# 6. Điểm khác biệt cốt lõi

CodeHehe không được định vị là bản sao LeetCode.

Điểm khác biệt dài hạn:

```text
Coding Challenge
+ 1v1 Competition
+ Energy
+ Skills
+ Defense
+ Minigames
+ Elo
+ Rank
```

Ý nghĩa từng phần:

* **Coding Challenge:** Năng lực lập trình vẫn là yếu tố cốt lõi.
* **1v1 Competition:** Người học không chỉ giải bài một mình mà đối đầu trực tiếp.
* **Energy:** Việc giải bài tạo tài nguyên chiến thuật.
* **Skills:** Người chơi có thể tác động tới nhịp trận của đối thủ.
* **Defense:** Đối thủ có quyền phản ứng, không chỉ bị tấn công thụ động.
* **Minigames:** Một số hiệu ứng tạo gián đoạn ngắn, có kiểm soát.
* **Elo và Rank:** Tạo động lực thi đấu dài hạn.

Nguyên tắc sản phẩm:

> Coding phải tiếp tục là yếu tố quyết định chính. Skills chỉ tạo chiến thuật và biến động, không được biến trận đấu thành trò may rủi không liên quan đến năng lực lập trình.

---

# 7. Chiến lược triển khai tổng thể

Quyết định chiến lược chính thức:

> Đơn giản hóa công nghệ trong V1 nhưng không loại bỏ định hướng Energy và Skills.

V1 không triển khai toàn bộ gameplay dài hạn.

Lộ trình:

```text
V1: Coding Battle Core
→ V1.5: Energy Core
→ V2: Skill Battle
→ V2.5: Defensive Skills
→ V3: Minigames
→ V4: Competitive System
```

Lý do:

* Thời gian chỉ khoảng bốn tuần.
* Đội ngũ chưa có nền tảng full-stack.
* Judge0 và battle flow đã là những phần có rủi ro cao.
* Core battle phải chạy ổn định trước khi thêm gameplay nâng cao.
* Một hệ thống nhỏ do nhóm làm chủ tốt hơn một hệ thống phức tạp chỉ Codex hiểu.
* V1 phải chứng minh được nền tảng coding battle để Energy và Skills có nơi phát triển.

---

# 8. Gameplay Master đã được định hướng

## 8.1. Trận đấu

Các nguyên tắc gameplay nền:

* Trận đấu 1v1.
* Hai người nhận cùng một danh sách bài.
* Danh sách bài phải được cố định khi trận bắt đầu.
* Mỗi người có progression độc lập.
* Người này giải xong bài không làm người kia tự động chuyển bài.
* Python là ngôn ngữ duy nhất trong V1.
* Hidden tests được sử dụng để chấm chính thức.
* Server quyết định thời gian, điểm và kết quả.
* Trạng thái quan trọng được lưu trong database.
* Refresh trang không được làm mất trạng thái trận.

## 8.2. Số lượng bài

Trong kiến trúc và gameplay ban đầu, V1 được định hướng có khoảng **4–5 bài mỗi trận**.

Trong một số ví dụ kế hoạch đơn giản hóa, con số **3 bài** được dùng để minh họa.

Quy tắc tài liệu:

* Con số 3 bài trong các ví dụ không được tự động coi là thay thế Gameplay Specification.
* Nếu Gameplay Specification chính thức đã chốt 4–5 bài, sử dụng 4–5 bài.
* Nếu nhóm muốn giảm xuống 3 bài để demo, phải ghi thành Change Request.
* Không để Codex tự quyết định số bài.

## 8.3. Độ khó bài

Định hướng dài hạn:

* Một hoặc hai bài đầu nên là bài Easy.
* Mục đích là giúp người chơi sớm hoàn thành bài.
* Ở phiên bản Energy, các bài đầu giúp người chơi nhanh chóng nhận Energy và tham gia gameplay skill.
* Bài sau có thể tăng độ khó.

## 8.4. Điểm cơ bản

* Mỗi bài có số điểm cơ bản.
* Điểm bài được cấu hình trong ngân hàng đề.
* Một người chỉ nhận điểm cơ bản một lần cho cùng một bài trong cùng một trận.
* Submit lại bài đã Accepted không được cộng thêm điểm.
* Frontend không được gửi điểm lên server.

Các ví dụ từng được sử dụng:

* Easy: 1 điểm.
* Medium: 2 điểm.
* Hard: 3 điểm.

Đây là cấu hình gameplay hợp lý, nhưng giá trị chính thức phải nằm trong Gameplay Specification hoặc dữ liệu Problem, không hard-code phân tán.

## 8.5. First-solve bonus

Quyết định cuối cùng:

> V1 có First-solve bonus. Người Accepted một bài trước đối thủ nhận thêm 1 điểm.

Luật chi tiết:

* Base score được cộng khi người chơi Accepted bài lần đầu.
* Người Accepted bài đó trước đối thủ nhận thêm `+1`.
* Mỗi bài chỉ có tối đa một First-solve winner.
* Submit lại bài đã giải không tạo thêm bonus.
* First-solve không được xác định bằng thứ tự Judge0 hoàn thành.
* First-solve phải dựa trên thời điểm server nhận submission hợp lệ.
* Field thời gian nên dùng ý nghĩa tương đương `received_at`.
* Judge0 có thể trả kết quả của submission sau trước submission trước.
* Backend phải xử lý trường hợp Judge0 hoàn thành không đúng thứ tự.
* Backend phải chống cộng bonus hai lần.
* Scoring phải idempotent.
* Phải có transaction hoặc cơ chế khóa/constraint phù hợp.
* Phải có test cho hai submission gần đồng thời.
* Submission gửi sau khi thời gian trận kết thúc không được tính điểm.

Ví dụ:

Một bài có 2 điểm cơ bản:

* Player A Accepted trước: 3 điểm.
* Player B Accepted sau: 2 điểm.
* Player A submit lại: 0 điểm bổ sung.
* Player B submit lại: 0 điểm bổ sung.

## 8.6. Energy

Định hướng V1.5:

* Hoàn thành một bài nhận `1 Energy`.
* Energy tối đa là `3`.
* Submit lại bài đã giải không tạo thêm Energy.
* Energy được lưu theo từng người chơi trong từng trận.
* Energy là tài nguyên để sử dụng Hint hoặc Skills.
* Backend quyết định việc tăng và trừ Energy.
* Frontend chỉ hiển thị.

## 8.7. Hint

* Sử dụng một Hint tiêu hao `1 Energy`.
* Hint chưa nằm trong V1.
* Hint thuộc V1.5 cùng Energy Core.

## 8.8. Skills

* Người chơi ban đầu chưa có skill hoặc chưa thể dùng skill ngay đầu trận.
* Một hoặc hai bài Easy đầu trận giúp tạo Energy.
* Người chơi dùng Energy để kích hoạt skill.
* Backend phải kiểm tra:

  * Trận đang diễn ra.
  * Người sử dụng thuộc trận.
  * Mục tiêu thuộc trận.
  * Người chơi đủ Energy.
  * Skill đang được phép dùng.
  * Skill không vượt giới hạn sử dụng.
  * Effect không bị tạo trùng bất hợp lệ.
* Frontend chỉ hiển thị effect.
* Frontend không được tự quyết định skill hợp lệ.

Các ý tưởng attack skill từng được đề xuất:

* Che một phần đề trong thời gian ngắn.
* Khóa Submit trong thời gian ngắn.
* Làm nhiễu hoặc thay đổi giao diện tạm thời.
* Kích hoạt mini challenge.
* Tác động tới nhịp giải bài của đối thủ.

Nguyên tắc:

* Tránh sửa trực tiếp source code của đối thủ.
* Không tạo hiệu ứng phá hủy công sức người chơi.
* Hiệu ứng phải có thời hạn và có thể kiểm soát.
* Skills không được làm coding mất vai trò trung tâm.

Danh sách attack skill chính thức chưa được chốt hoàn toàn và phải được thiết kế trong V2.

## 8.9. Defense

Ba cơ chế phòng thủ đã được giữ lại:

### Cleanse

* Xóa hoàn toàn hiệu ứng bất lợi đang tồn tại.

### Reflect

* Phản lại hiệu ứng cho người sử dụng ban đầu.

### Shield

* Tạo khiên bảo vệ trước một hiệu ứng bất lợi tiếp theo.
* Khiên có thể được tiêu thụ sau một lần chặn.

Các cơ chế phòng thủ khác từng được đề xuất đã bị loại khỏi định hướng hiện tại.

## 8.10. Minigames

Các minigame đã được định hướng:

* Flappy Bird.
* Trò chơi khủng long khi mất mạng.
* Giải một câu toán.
* Gõ đúng một chuỗi ký tự.

Nguyên tắc triển khai:

* Minigame có thể chạy chủ yếu ở trình duyệt.
* Backend lưu challenge:

  * Người bị challenge.
  * Loại challenge.
  * Thời điểm bắt đầu.
  * Thời gian hết hạn.
  * Trạng thái hoàn thành.
* Minigame chưa nằm trong V1.
* Minigame dự kiến nằm ở V3.

## 8.11. Skip

Gameplay dài hạn có định hướng:

* Mỗi người có thể có một lượt bỏ qua bài.

Tuy nhiên, cơ chế chưa được chốt vì có rủi ro:

* Làm lệch danh sách bài giữa hai người.
* Tạo dependency không ổn định giữa các bài.
* Làm sai công bằng về điểm hoặc độ khó.
* Ảnh hưởng cơ chế cùng một danh sách bài.

Quyết định:

* Skip không nằm trong V1.
* Không triển khai cho đến khi có rule đầy đủ.
* Cần tiếp tục nghiên cứu cách skip mà không phá frozen problem list và independent progression.

## 8.12. Elo và xếp hạng

* Phiên bản sau sử dụng Elo.
* Elo không nằm trong V1.
* Elo dự kiến thuộc V4 cùng rank, leaderboard và matchmaking.
* Rating phải do backend tính sau trận.
* V1 nên giữ `MatchPlayer` đủ sạch để sau này thêm `rating_before` và `rating_after`.

---

# 9. Phạm vi V1 chính thức

V1 là **Coding Battle Core**.

## 9.1. Tài khoản

V1 phải có:

* Đăng ký.
* Đăng nhập.
* Đăng xuất.
* Xác định người chơi hiện tại.
* Bảo vệ các trang yêu cầu đăng nhập.

Công nghệ:

* Django Auth.
* Django Session.

Không dùng JWT trong V1.

## 9.2. Ngân hàng đề

Admin có thể:

* Tạo bài.
* Sửa bài.
* Xóa hoặc vô hiệu hóa bài.
* Nhập nội dung đề.
* Cấu hình độ khó.
* Cấu hình điểm.
* Cấu hình starter code.
* Thêm sample tests.
* Thêm hidden tests.
* Thiết lập thứ tự hoặc trạng thái active.

Người chơi:

* Chỉ thấy nội dung đề và sample tests.
* Không thấy hidden tests.
* Không được nhận hidden tests trong HTML hoặc JSON.

Admin sử dụng Django Admin.

Không xây custom admin UI trong V1.

## 9.3. Phòng đấu

V1 sử dụng mã phòng, không dùng automatic matchmaking.

Flow:

1. Player A đăng nhập.
2. Player A tạo phòng.
3. Hệ thống sinh room code.
4. Player A trở thành host.
5. Player B nhập room code.
6. Backend kiểm tra phòng.
7. Player B được thêm vào.
8. Người thứ ba bị từ chối.
9. Host bắt đầu khi đủ hai người.

Quyết định:

* Một phòng tối đa hai người.
* Waiting Room có thể tối giản.
* Không cần queue.
* Không cần Redis.
* Không cần presence system phức tạp.
* Không cần ready check phức tạp trong V1.
* Host là người bắt đầu trận khi đủ hai người.

## 9.4. Trận đấu

V1 phải hỗ trợ:

* Hai người nhận cùng danh sách bài.
* Danh sách bài được cố định khi trận bắt đầu.
* Mỗi người có progression độc lập.
* Python only.
* Timer phía server.
* Submit trong trận.
* Điểm cơ bản.
* First-solve `+1`.
* Polling trạng thái.
* Refresh và quay lại trận.
* Lưu kết quả.

## 9.5. Submit code

Frontend gửi:

* Problem ID.
* Source code.
* Match ID thông qua URL hoặc context xác thực.

Backend phải:

1. Xác thực user.
2. Kiểm tra user thuộc trận.
3. Kiểm tra trận đang `PLAYING`.
4. Kiểm tra thời gian chưa hết.
5. Kiểm tra Problem thuộc MatchProblem.
6. Lấy hidden tests.
7. Gọi JudgeService.
8. JudgeService gọi Judge0.
9. Chuẩn hóa verdict.
10. Lưu Submission.
11. Xử lý scoring nếu Accepted.
12. Chống xử lý scoring trùng.
13. Trả JSON cho frontend.

Tuyệt đối không:

* Dùng `exec()`.
* Dùng `eval()`.
* Chạy source code trực tiếp trong Django process.
* Gửi hidden tests về frontend.
* Cho frontend tự khai báo Accepted.

## 9.6. Verdict

Các verdict nội bộ nên được chuẩn hóa:

```text
PENDING
ACCEPTED
WRONG_ANSWER
COMPILATION_ERROR
RUNTIME_ERROR
TIME_LIMIT_EXCEEDED
INTERNAL_ERROR
```

Có thể lưu thêm:

* Judge token.
* Runtime.
* Memory.
* Error message.

Runtime và memory visualization không phải ưu tiên V1 nếu gây chậm tiến độ.

## 9.7. Polling

V1 sử dụng polling JavaScript thay vì WebSocket.

Endpoint chính:

```text
GET /matches/<match_id>/state/
```

Tần suất:

* Playing Match: khoảng 1 giây/lần.
* Waiting Room: khoảng 2 giây/lần.
* Khi tab bị ẩn: có thể giảm còn 3–5 giây/lần.
* Khi Match đã Finished: dừng polling.
* Khi người dùng rời trang: dừng polling.
* Khi request lỗi liên tục: backoff hoặc dừng có kiểm soát.

State endpoint trả dữ liệu tối thiểu:

* Match status.
* Server time hoặc remaining seconds.
* Điểm của mình.
* Điểm đối thủ.
* Bài mình đã giải.
* Tiến độ đối thủ.
* Winner nếu trận kết thúc.
* Các field gameplay tương lai khi cần.

State endpoint không được:

* Trả source code.
* Trả hidden tests.
* Trả toàn bộ Submission history.
* Gọi Judge0.
* Ghi database mỗi lần polling.
* Tạo record mới.
* Thực hiện N+1 query.

Mục tiêu query:

* Khoảng 3–6 query cố định/request.
* Số query không tăng tuyến tính theo số bài.
* Sử dụng `select_related`, `prefetch_related`, `values` hoặc `values_list` khi phù hợp.

Không thêm Redis chỉ để tối ưu sớm khi chưa chứng minh có vấn đề.

## 9.8. Timer

* Timer phía server là nguồn sự thật.
* Match lưu `started_at`.
* Match lưu duration hoặc `ends_at`.
* Remaining time được tính từ thời gian server.
* Frontend có thể hiển thị countdown nhưng không quyết định trận đã hết hay chưa.
* Submission gửi sau hạn phải bị từ chối.
* Refresh không được reset timer.

## 9.9. Kết quả trận

Khi hết giờ hoặc đạt điều kiện kết thúc:

* Match chuyển sang `FINISHED`.
* Server từ chối submission mới.
* Điểm cuối được tính.
* Winner được xác định.
* `ended_at` được lưu.
* Kết quả được trả cho hai client.
* Trang Result hiển thị thắng, thua hoặc hòa.

Tie-break chính xác phải theo Gameplay Specification. Không được để Codex tự chọn quy tắc tie-break.

---

# 10. Ngoài phạm vi V1

Các tính năng sau chưa triển khai trong V1:

* Energy.
* Hint tiêu hao Energy.
* Attack Skills.
* Defensive Skills.
* Inventory.
* Minigames.
* Elo.
* Rank.
* Leaderboard.
* Match history đầy đủ.
* Automatic matchmaking.
* Redis.
* WebSocket.
* React SPA.
* Tournament.
* Team battle.
* Nhiều ngôn ngữ lập trình.
* Spectator.
* Chat.
* Economy.
* Custom admin UI.
* Complex ready system.
* Rematch nếu core chưa ổn.
* Profile nâng cao.
* Animation phức tạp.
* Mobile application.
* Microservices.
* Distributed worker architecture.

Các tính năng này không bị loại bỏ khỏi Product Vision. Chúng chỉ không được phép làm chậm core V1.

---

# 11. Lịch sử kiến trúc và quyết định thay thế

## 11.1. Kiến trúc FastAPI ban đầu

Plan ban đầu từng sử dụng:

* FastAPI.
* React.
* Vite.
* PostgreSQL.
* Redis.
* Judge0 CE.
* Socket.IO.
* Docker Compose.
* Một VPS.
* Python only.
* SQLAlchemy async.
* Alembic.
* JWT.
* SQLAdmin.
* Zustand.
* OpenAPI/Hey API.
* Snapshot API.
* Realtime socket events.
* Redis matchmaking.
* First-solve transaction.
* Server-authoritative timer.
* Frozen problem versions.

Kiến trúc FastAPI ban đầu còn có các module:

```text
auth
users
problems
matchmaking
matches
submissions
realtime
ratings
admin
```

Các quyết định đúng trong kiến trúc cũ:

* Không dùng microservices cho app chính.
* Không dùng Celery.
* Không dùng RabbitMQ.
* Redis chỉ dùng queue, presence và matchmaking lock.
* PostgreSQL là authoritative state.
* Hidden tests không lộ.
* Match problems được frozen.
* First-solve dựa trên submission received time.
* Socket chỉ phát delta sau DB commit.
* Snapshot được dùng để reconnect.
* Judge0 chịu trách nhiệm chạy code.
* SQLAdmin dùng để tránh viết custom admin.
* FakeJudgeService dùng để phá dependency.
* Có test cho race condition và duplicate scoring.

## 11.2. Lý do từ bỏ FastAPI V1

Kiến trúc FastAPI không sai về kỹ thuật, nhưng không phù hợp với nhóm hiện tại vì yêu cầu hiểu và tích hợp quá nhiều thành phần:

* Frontend và backend tách biệt.
* API contract.
* JSON schema.
* Pydantic.
* SQLAlchemy async.
* PostgreSQL.
* Alembic.
* JWT.
* CORS.
* React lifecycle.
* Frontend state management.
* Socket.IO.
* Redis.
* Reconnect.
* Race condition.
* Transaction.
* Deployment nhiều service.

Rủi ro chính:

* Codex có thể code được nhưng nhóm không kiểm soát được.
* Khó giải thích trước hội đồng.
* Khó debug khi lỗi frontend/backend.
* Timeline bốn tuần dễ bị phá vỡ.
* Công nghệ trở thành điểm yếu thay vì điểm mạnh.

## 11.3. Quyết định thay thế

Quyết định cuối cùng:

> V1 chuyển sang Django monolith.

Kiến trúc Django không phải phương án tạm để vứt bỏ. Django được giữ làm nền backend có thể phát triển qua các phiên bản Energy, Skills, WebSocket, PostgreSQL và React sau này.

---

# 12. Kiến trúc V1 đang có hiệu lực

## 12.1. Stack

* Backend: Django monolith.
* Frontend: Django Templates.
* JavaScript: Vanilla JavaScript.
* Database: SQLite.
* ORM: Django ORM.
* Migration: Django migrations.
* Authentication: Django Auth và Session.
* Admin: Django Admin.
* Near realtime: Polling.
* Code execution: Judge0.
* Submission language: Python.
* Source control: Git và GitHub.
* Development environment: Python virtual environment.
* Deployment: Một Django application và Judge0 bên ngoài hoặc self-host sau khi đánh giá.

## 12.2. Công nghệ không sử dụng trong V1

* FastAPI.
* React.
* Vite.
* TypeScript.
* Zustand.
* PostgreSQL.
* Redis.
* Socket.IO.
* JWT.
* SQLAlchemy.
* Alembic.
* SQLAdmin.
* Celery.
* RabbitMQ.
* Microservices.
* OpenAPI client generation.
* Kubernetes.
* Azure Service Bus.
* Azure Functions cho core flow.
* Azure Redis.
* Matchmaking queue.

## 12.3. Lý do chọn Django

Django cung cấp sẵn:

* Auth.
* Session.
* ORM.
* Migration.
* Templates.
* Admin.
* Form handling.
* URL routing.
* Security defaults.

Django giúp giảm số công nghệ mà nhóm phải ghép.

Mục tiêu:

* Dễ học.
* Dễ giải thích.
* Dễ chạy local.
* Dễ chia module.
* Có đường nâng cấp.

---

# 13. Kiến trúc logic

```text
Browser
   │
   ├── HTML
   ├── CSS
   ├── Django Templates
   └── Vanilla JavaScript polling
            │
            ▼
         Django
   ├── accounts
   ├── problems
   ├── matches
   ├── submissions
   ├── gameplay
   ├── templates
   └── static
       │            │
       ▼            ▼
    SQLite        Judge0
```

## 13.1. Browser

Browser chịu trách nhiệm:

* Hiển thị HTML.
* Hiển thị CSS.
* Gửi form hoặc fetch request.
* Polling match state.
* Cập nhật UI.
* Hiển thị verdict.
* Hiển thị timer từ dữ liệu server.

Browser không chịu trách nhiệm:

* Chấm code.
* Quyết định điểm.
* Quyết định winner.
* Quyết định skill hợp lệ.
* Lưu authoritative match state.

## 13.2. Django

Django chịu trách nhiệm:

* Authentication.
* Authorization.
* Problem Bank.
* Room.
* Match.
* Submission.
* Scoring.
* Timer.
* Winner.
* Admin.
* Gọi Judge0.
* Lưu dữ liệu.
* Trả HTML hoặc JSON.

## 13.3. SQLite

SQLite lưu authoritative state V1.

SQLite phù hợp quy mô demo nhỏ nhưng có giới hạn:

* Concurrent writes hạn chế.
* Có thể gặp `database is locked`.
* Không phù hợp scale lớn.

Quyết định:

* V1 dùng SQLite.
* Không đưa Redis hoặc PostgreSQL vào sớm.
* Tránh ghi database trong polling.
* Nếu lỗi locking xuất hiện thường xuyên trong kiểm thử, cân nhắc chuyển PostgreSQL.
* V4 dự kiến dùng PostgreSQL.

## 13.4. Judge0

Judge0 chịu trách nhiệm:

* Chạy source code trong môi trường sandbox.
* Nhận stdin.
* Trả stdout.
* Trả status.
* Giới hạn thời gian.
* Xử lý runtime error.
* Tách việc thực thi code khỏi Django.

Django không được chạy code người dùng trực tiếp.

---

# 14. Nguyên tắc phân lớp

## 14.1. View

View chỉ:

* Nhận request.
* Xác thực và kiểm tra input cơ bản.
* Gọi service.
* Trả HTML hoặc JSON.
* Xử lý response/error phù hợp.

View không được chứa toàn bộ gameplay.

Không nên:

```text
View
→ lấy test
→ gọi Judge0
→ tính điểm
→ tính Energy
→ xử lý skill
→ xác định winner
→ render
```

## 14.2. Service

Service chứa business logic.

Các service dự kiến:

* JudgeService.
* SubmissionService.
* ScoringService.
* MatchService.
* RoomService.
* EnergyService.
* SkillService.
* EffectService.
* ChallengeService.
* RatingService.

V1 sử dụng:

* JudgeService.
* SubmissionService.
* ScoringService.
* MatchService hoặc RoomService.

## 14.3. Model

Model:

* Lưu trạng thái.
* Định nghĩa relation.
* Định nghĩa enum/status.
* Đặt unique constraint.
* Bảo vệ tính toàn vẹn dữ liệu.

## 14.4. Template

Template:

* Chỉ hiển thị dữ liệu.
* Không tính điểm.
* Không quyết định winner.
* Không quyết định trận hết giờ.
* Không chứa gameplay logic.

## 14.5. JavaScript

JavaScript:

* Gửi fetch request.
* Polling.
* Cập nhật DOM.
* Hiển thị loading/error.
* Dừng polling đúng lúc.

JavaScript không phải nguồn sự thật.

---

# 15. Cấu trúc Django dự kiến

```text
codehehe/
├── config/
├── accounts/
├── problems/
├── matches/
├── submissions/
├── gameplay/
├── templates/
├── static/
├── docs/
├── tests/ hoặc test theo từng app
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 15.1. config

* Django settings.
* Root URLs.
* WSGI/ASGI.
* Environment config.
* Shared project configuration.

## 15.2. accounts

* Register.
* Login.
* Logout.
* Profile cơ bản nếu cần.
* Django Auth integration.

## 15.3. problems

* Problem.
* TestCase.
* Problem list/detail.
* Django Admin.
* Sample/hidden visibility.

## 15.4. matches

* Match.
* MatchPlayer.
* MatchProblem.
* PlayerProblemProgress.
* Create Room.
* Join Room.
* Start Match.
* Finish Match.
* Match state.

## 15.5. submissions

* Submission.
* Submit endpoint.
* JudgeService.
* Judge0 client.
* Verdict mapping.
* Submission validation.

## 15.6. gameplay

* ScoringService trong V1.
* EnergyService trong V1.5.
* SkillService trong V2.
* EffectService trong V2/V2.5.
* ChallengeService trong V3.
* RatingService trong V4.

---

# 16. Database V1 dự kiến

Django sử dụng User model có sẵn.

Database Design chính thức vẫn phải được viết và chốt trong hai ngày đầu. Các model sau là baseline đã thống nhất.

## 16.1. User

Sử dụng Django User.

Mục đích:

* Authentication.
* Liên kết player với MatchPlayer.
* Liên kết Submission.
* Admin permission.

V1 không cần custom user phức tạp nếu không có lý do bắt buộc.

## 16.2. Problem

Field dự kiến:

* `title`.
* `statement`.
* `difficulty`.
* `points`.
* `starter_code`.
* `order`.
* `is_active`.
* `created_at`.
* `updated_at`.

Mục đích:

* Lưu đề.
* Cấu hình điểm.
* Phân loại độ khó.
* Bật/tắt đề.

## 16.3. TestCase

Field dự kiến:

* `problem`.
* `input_data`.
* `expected_output`.
* `is_sample`.
* `order`.

Quy tắc:

* Sample test được hiển thị.
* Hidden test không xuất hiện ở frontend.
* TestCase thuộc đúng một Problem.

## 16.4. Match

Field dự kiến:

* `room_code`.
* `host`.
* `status`.
* `started_at`.
* `ended_at`.
* `duration_seconds` hoặc `ends_at`.
* `winner`.
* `created_at`.

Status dự kiến:

```text
WAITING
PLAYING
FINISHED
CANCELLED
```

Quy tắc:

* Room code phải đủ khả năng phân biệt phòng active.
* Một Match có tối đa hai MatchPlayer.
* Chỉ host được Start trong V1.
* Chỉ Start khi đủ hai người.

## 16.5. MatchPlayer

Field V1:

* `match`.
* `user`.
* `score`.
* `joined_at`.
* `finished_at` nếu cần.

Constraint:

* Một user chỉ có một MatchPlayer trong cùng một Match.
* Một Match tối đa hai player ở service/business rule.

Field tương lai:

* `energy`.
* `max_energy`.
* `rating_before`.
* `rating_after`.
* `shield`.
* Current effect state nếu dùng dạng field, dù hướng khuyến nghị là effect model.

MatchPlayer phải tồn tại từ V1 để giữ đường nâng cấp gameplay.

## 16.6. MatchProblem

Field dự kiến:

* `match`.
* `problem`.
* `order`.
* `points_snapshot`.
* `first_solver_player` hoặc field/quan hệ tương đương nếu Database Design chọn cách này.
* Có thể lưu first-solve timestamp.

Quy tắc:

* Danh sách bài được tạo khi Start Match.
* Không lấy random lại trong trận.
* MatchProblem freeze danh sách bài.
* Nên snapshot điểm để việc sửa Problem sau đó không làm đổi điểm trận.
* V1 không xây đầy đủ ProblemVersion.
* Quy tắc vận hành: không chỉnh sửa đề đang được dùng trong trận active.
* Problem versioning đầy đủ có thể thêm ở phiên bản sau.

## 16.7. Submission

Field dự kiến:

* `match`.
* `player`.
* `problem` hoặc `match_problem`.
* `source_code`.
* `verdict`.
* `received_at`.
* `completed_at`.
* `scoring_processed`.
* `judge_token`.
* `runtime`.
* `memory`.
* `error_message`.

Quy tắc:

* `received_at` là cơ sở xác định thứ tự First-solve.
* Không dùng Judge completion order.
* `scoring_processed` hỗ trợ idempotency.
* Submission phải lưu cả trường hợp sai.

## 16.8. PlayerProblemProgress

Field dự kiến:

* `match`.
* `player`.
* `problem` hoặc `match_problem`.
* `is_solved`.
* `solved_at`.
* `points_awarded`.
* `first_solve_bonus_awarded`.

Constraint:

* Unique trên `match + player + problem`.
* Một người chỉ có một progress record cho một bài trong một trận.
* Một bài chỉ tính điểm một lần cho một người.

## 16.9. Models tương lai

### Skill

* Name.
* Code.
* Description.
* Type.
* Energy cost.
* Duration.
* Active status.

### MatchPlayerSkill

* MatchPlayer.
* Skill.
* Quantity.
* Used count.

### SkillEffect

* Match.
* Source player.
* Target player.
* Skill.
* Status.
* Started at.
* Expires at.
* Remaining uses.

### MiniChallenge

* Match.
* Player.
* Challenge type.
* Payload.
* Status.
* Started at.
* Expires at.
* Completed at.

---

# 17. Interface Contract sơ bộ

Interface Contract chính thức chưa được viết, nhưng các route sau đã được định hướng.

## 17.1. HTML routes

```text
/register/
/login/
/logout/
/lobby/
/problems/<id>/
/matches/<id>/
/matches/<id>/result/
```

Có thể dùng route room riêng:

```text
/room/<code>/
```

hoặc waiting room qua Match ID tùy System Design.

## 17.2. Action routes

```text
POST /rooms/create/
POST /rooms/join/
POST /matches/<id>/start/
POST /matches/<id>/submit/
```

## 17.3. State route

```text
GET /matches/<id>/state/
```

Response tối thiểu:

```json
{
  "status": "playing",
  "remaining_seconds": 438,
  "my_score": 3,
  "opponent_score": 2,
  "my_solved_problem_ids": [12, 15],
  "opponent_solved_problem_ids": [12],
  "winner_id": null
}
```

Errors dự kiến:

* `401`: Chưa đăng nhập.
* `403`: Không thuộc trận hoặc không có quyền.
* `404`: Match hoặc Problem không tồn tại.
* `409`: Trạng thái hiện tại không cho phép hành động.
* `400`: Input không hợp lệ.
* `503`: Judge tạm thời không khả dụng.

---

# 18. UI/UX phạm vi

## 18.1. Màn hình bắt buộc

* Register.
* Login.
* Lobby.
* Waiting Room.
* Battle.
* Result.
* Django Admin.

## 18.2. Battle layout định hướng

### Khu vực trái

* Danh sách bài.
* Nội dung đề.
* Sample tests.

### Khu vực giữa

* Code editor hoặc textarea.
* Submit button.
* Verdict/output panel.

### Khu vực phải

* Timer.
* Điểm của mình.
* Điểm đối thủ.
* Tiến độ của mình.
* Tiến độ đối thủ.

## 18.3. Editor

Quyết định:

* Ban đầu có thể dùng `<textarea>`.
* Chỉ thêm CodeMirror/Ace khi Submission Vertical Slice đã chạy.
* Không để editor làm chậm core flow.

## 18.4. UI states

Mỗi màn hình phải cân nhắc:

* Normal.
* Loading.
* Empty.
* Error.
* Disabled.
* Finished.
* Judge unavailable.
* Room full.
* Invalid room code.
* Match not started.
* Match expired.

## 18.5. Nguyên tắc thiết kế

* Giao diện clean.
* Không sao chép LeetCode.
* Không tạo UI “AI-generated” rối mắt.
* Ưu tiên hierarchy rõ.
* Ít màu.
* Không animation phức tạp trước khi core ổn.
* Waiting Room có thể đơn giản hóa tối đa nếu trễ tiến độ.

---

# 19. Môi trường phát triển local

## 19.1. Quyết định môi trường cuối cùng

Sau khi chuyển sang Django V1, môi trường local được đơn giản hóa.

Mỗi máy cần:

* Git.
* Python.
* VS Code.
* Trình duyệt Chrome hoặc Edge.

Extensions khuyến nghị:

* Python.
* Git.
* Ruff.
* GitLens.
* SQLite Viewer.
* Có thể dùng Thunder Client hoặc Postman, nhưng không bắt buộc.

## 19.2. Chưa cần cài ngay

* Docker Desktop.
* WSL.
* PostgreSQL.
* Redis.
* Node.js.
* React.
* Azure CLI.
* Kubernetes.

WSL và Docker từng nằm trong setup FastAPI cũ nhưng không còn là yêu cầu bắt buộc của Django V1.

Nếu Windows chạy Python ổn định, dùng trực tiếp Windows để giảm độ khó.

## 19.3. Python virtual environment

Mỗi người tạo môi trường riêng:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

## 19.4. Dependency khởi đầu

Dependency tối thiểu từng được đề xuất:

```bash
pip install django python-dotenv requests
```

Dependency chính xác và version phải được khóa trước khi cả ba bắt đầu phát triển.

Sau khi thống nhất:

```bash
pip freeze > requirements.txt
```

Không để ba máy sử dụng version khác nhau.

## 19.5. File bắt buộc

```text
requirements.txt
.env.example
.gitignore
README.md
```

Không commit:

```text
.env
.venv/
db.sqlite3
__pycache__/
```

Dùng seed script hoặc management command để tạo dữ liệu demo thay vì phụ thuộc database local của một thành viên.

## 19.6. Phiên bản chưa chốt

Các phiên bản sau chưa được chốt chính thức:

* Python version cụ thể.
* Django version cụ thể.
* Judge0 version cụ thể.
* Azure service cụ thể.

Quy tắc:

* Cả ba phải dùng cùng version.
* Không tự cài bản mới nhất không khóa.
* Ưu tiên version ổn định tương thích với nhau.
* Version phải được ghi trong Setup Guide.

---

# 20. Khởi tạo repository và Django

## 20.1. Repository

Dùng GitHub.

Repository phải có:

```text
docs/
README.md
requirements.txt
.env.example
.gitignore
```

Dùng GitHub Projects hoặc Trello để quản lý task.

## 20.2. Django skeleton

Khởi tạo:

```bash
django-admin startproject config .
```

Tạo app:

```bash
python manage.py startapp accounts
python manage.py startapp problems
python manage.py startapp matches
python manage.py startapp submissions
python manage.py startapp gameplay
```

Chạy:

```bash
python manage.py migrate
python manage.py runserver
```

## 20.3. Health endpoint

Tạo:

```text
GET /health/
```

Response:

```json
{"status": "ok"}
```

Health endpoint là milestone đầu tiên để xác nhận môi trường đồng nhất trên ba máy và triển khai Azure sau này.

## 20.4. Base frontend

Tạo:

```text
templates/base.html
static/css/
static/js/
```

Cả ba máy phải chạy được cùng một giao diện base.

---

# 21. Judge0 — rủi ro kỹ thuật lớn nhất

## 21.1. Mức độ

Judge0 là Gate quan trọng nhất của sản phẩm.

Nếu Judge0 không hoạt động, CodeHehe không còn coding judge thực sự.

## 21.2. Quyết định thời gian

* Judge Spike bắt đầu cuối Tuần 1.
* Judge0 thật phải chạy chậm nhất đầu hoặc giữa Tuần 2.
* Không được đẩy Judge0 sang Tuần 3.
* Nếu Judge0 trượt, cả nhóm phải ưu tiên giải quyết.
* FakeJudgeService được dùng để các module khác không bị block.

## 21.3. JudgeService interface

Judge0 phải nằm sau một interface.

Ví dụ ý tưởng:

```python
class JudgeService:
    def judge(self, source_code, test_cases):
        ...
```

Hai implementation:

```text
FakeJudgeService
Judge0Service
```

Mục tiêu:

* UI và Submission flow có thể xây trước bằng FakeJudge.
* Khi Judge0 sẵn sàng, thay implementation mà không sửa toàn bộ app.

## 21.4. Test bắt buộc

### Accepted

Code đúng.

### Wrong Answer

Code chạy nhưng output sai.

### Compilation/Syntax Error

Code Python lỗi cú pháp.

### Runtime Error

Ví dụ chia cho 0.

### Time Limit Exceeded

```python
while True:
    pass
```

### Output quá dài

Không được làm treo Django.

### Network error

Judge0 không phản hồi hoặc mất kết nối.

### Nhiều test case

Một submission chạy nhiều hidden test.

### Concurrent requests

Có test nhỏ với nhiều submission gần nhau.

## 21.5. Definition of Done Judge Spike

```text
□ Code đúng trả Accepted
□ Code sai trả Wrong Answer
□ Code lỗi cú pháp được nhận diện
□ Runtime Error được nhận diện
□ while True bị timeout
□ Output quá dài không làm treo hệ thống
□ Judge0 lỗi mạng được xử lý có kiểm soát
□ Có FakeJudgeService cùng interface
```

## 21.6. External hay self-host

Hai hướng:

### Judge0 endpoint bên ngoài

Ưu điểm:

* Setup nhanh.
* Phù hợp connectivity spike.

Rủi ro:

* Rate limit.
* Phụ thuộc mạng.
* Không kiểm soát hoàn toàn.

### Self-host Judge0

Ưu điểm:

* Chủ động.
* Phù hợp demo lâu dài.

Rủi ro:

* Setup phức tạp.
* Tốn Azure credit.
* Tốn thời gian.
* Có thể cần Linux/Docker.

Quyết định hiện tại:

* Chứng minh integration trước bằng phương án nhanh nhất hợp lệ.
* Không self-host Judge0 ngay ngày đầu.
* Hướng deploy Judge0 chính thức phải được chốt sau Judge Spike.
* Nếu cần self-host, Azure có thể được dùng sau khi app core đã hoạt động.

---

# 22. Roadmap triển khai tổng thể

```text
Giai đoạn 0 — Chốt thiết kế tối thiểu
Giai đoạn 1 — Chuẩn hóa môi trường ba máy
Giai đoạn 2 — Khởi tạo repository và Django
Giai đoạn 3 — Auth và ngân hàng đề
Giai đoạn 4 — Judge Spike
Giai đoạn 5 — Submission Vertical Slice
Giai đoạn 6 — Match Foundation
Giai đoạn 7 — Playable Battle
Giai đoạn 8 — Tích hợp và kiểm thử
Giai đoạn 9 — Deploy Azure
Giai đoạn 10 — Hoàn thiện demo
```

---

# 23. Giai đoạn 0 — Chốt thiết kế tối thiểu

## Thời lượng

Tối đa hai ngày đầu.

Tài liệu không được trở thành blocker hành chính kéo dài.

## Phải hoàn thành

### System Design V1

Chốt:

* Django apps.
* Vai trò từng app.
* Layer boundaries.
* Submit flow.
* Match flow.
* Polling flow.
* JudgeService interface.
* Server-authoritative rules.

Mục tiêu độ dài:

* Khoảng 4–7 trang Markdown.

### Database Design V1

Chốt:

* Models.
* Fields quan trọng.
* Relations.
* Status.
* Unique constraints.
* First-solve data.
* Snapshot data.
* Field chuẩn bị cho Energy.

Mục tiêu:

* Khoảng 4–6 trang Markdown.
* Có ERD.

### Interface Contract tối thiểu

Chốt:

* Routes.
* Request.
* Response.
* Error.
* Authentication.

### Wireframe tối thiểu

Chốt sáu màn hình:

* Login.
* Register.
* Lobby.
* Waiting Room.
* Battle.
* Result.

## Việc có thể làm song song

Trong khi viết tài liệu:

* Cài Git.
* Cài Python.
* Cài VS Code.
* Tạo repository.
* Tạo virtual environment.
* Nghiên cứu Judge0 bằng script độc lập.
* Tạo base template.
* Tạo project board.

## Không làm trước khi Database Design chốt

* Tạo hàng loạt model.
* Viết scoring hoàn chỉnh.
* Viết match state hoàn chỉnh.
* Prompt Codex xây toàn bộ backend.
* Tự thêm model.

---

# 24. Giai đoạn 1 — Chuẩn hóa môi trường

Mục tiêu:

* Ba máy dùng cùng Python.
* Ba máy dùng cùng Django.
* Ba máy clone cùng repository.
* Ba máy chạy cùng lệnh.
* Không có dependency trôi nổi.

Milestone:

```text
python --version
git --version
python manage.py runserver
```

đều hoạt động trên ba máy.

---

# 25. Giai đoạn 2 — Django skeleton

## Thành viên A

* Tạo Django project.
* Settings.
* Apps.
* Root URLs.
* Migration.
* Health endpoint.

## Thành viên B

* `base.html`.
* CSS structure.
* Navbar placeholder.
* Layout container.

## Thành viên C

* JudgeService interface.
* FakeJudgeService.
* Test FakeJudge.

Milestone:

```text
/health/
/admin/
```

chạy được trên cả ba máy.

---

# 26. Giai đoạn 3 — Auth và Problem Bank

Mục tiêu vertical slice:

```text
Admin tạo đề
→ Player đăng nhập
→ Player xem được đề
```

## Thành viên A

* Register.
* Login.
* Logout.
* Protected route.
* Problem model.
* TestCase model.
* Migration.
* Django Admin.

## Thành viên B

* Register template.
* Login template.
* Lobby template.
* Problem list/detail.
* Hiển thị sample tests.
* Không hiển thị hidden tests.

## Thành viên C

Tests:

* User register.
* User login.
* Guest không vào protected page.
* Sample test hiển thị.
* Hidden test không có trong response.
* FakeJudge chuẩn bị verdict.

Milestone cuối giai đoạn:

```text
Admin login
→ tạo Problem
→ thêm sample + hidden tests
→ Player login
→ chỉ thấy sample tests
```

---

# 27. Giai đoạn 4 — Judge Spike

Thực hiện cuối Tuần 1 hoặc đầu Tuần 2.

Mục tiêu:

```text
Source code
→ JudgeService
→ Judge0
→ normalized verdict
```

Không cần UI đẹp trong spike.

---

# 28. Giai đoạn 5 — Submission Vertical Slice

Mục tiêu:

```text
Player xem đề
→ nhập code
→ submit
→ hidden tests
→ verdict
→ lưu Submission
```

## Thành viên A

* Submission model.
* Migration.
* Relations.
* Admin inspection nếu cần.

## Thành viên B

* Textarea/editor.
* Submit button.
* Loading state.
* Verdict panel.
* Error message.

## Thành viên C

* SubmissionService.
* Judge0Service.
* Hidden test execution.
* Verdict mapping.
* Error handling.
* Tests.

Gate 1:

```text
Submit Python
→ hidden tests
→ verdict
→ lưu Submission
```

Deadline:

* Giữa hoặc cuối Tuần 2.
* Không được để sang Tuần 3.

Nếu chưa qua Gate 1:

* Dừng animation.
* Dừng profile.
* Dừng leaderboard.
* Không xây Energy.
* Không xây Skills.
* Tập trung Judge.

---

# 29. Giai đoạn 6 — Match Foundation

Nên bắt đầu cuối Tuần 2.

Models:

* Match.
* MatchPlayer.
* MatchProblem.
* PlayerProblemProgress.

## Thành viên A

* Models.
* Constraints.
* Room code generator.
* Create Room.
* Join Room.
* Start Match service.

## Thành viên B

* Lobby.
* Room code form.
* Waiting Room tối giản.
* Hiển thị hai người.
* Host Start button.

## Thành viên C

Tests:

* Create Room.
* Join Room.
* Invalid code.
* Third player rejected.
* Host start thiếu người.
* MatchProblem freeze.

Gate 2:

```text
A tạo phòng
→ B nhập mã
→ cả hai ở cùng Match
→ người thứ ba bị từ chối
```

Deadline:

* Cuối Tuần 2.

---

# 30. Giai đoạn 7 — Playable Battle

Mục tiêu:

* Ghép Submission vào Match.
* Có Score.
* Có First-solve.
* Có Timer.
* Có Polling.
* Có Result.

## Thành viên A

* Validate user thuộc Match.
* Validate Problem thuộc MatchProblem.
* Timer server.
* Finish Match.
* Winner.
* Refresh/re-entry.

## Thành viên B

* Battle UI.
* Polling.
* Timer display.
* Score display.
* Opponent progress.
* Result UI.

## Thành viên C

* ScoringService.
* Duplicate scoring protection.
* First-solve.
* Submission after timeout.
* Winner tests.
* Concurrency tests.

Gate 3:

```text
A tạo phòng
→ B join
→ host start
→ nhận cùng bài
→ submit
→ điểm cập nhật
→ timer
→ finish
→ result
```

Deadline:

* Cuối Tuần 3.

---

# 31. Timeline bốn tuần đã điều chỉnh

## Tuần 1 — Foundation và Judge Spike

### Ngày 1–2

* Chốt System Design.
* Chốt Database Design.
* Chốt Interface Contract tối thiểu.
* Chốt wireframe.
* Cài môi trường.
* Tạo repository.
* Tạo board.

### Ngày 3

* Django skeleton.
* Health endpoint.
* Base template.
* FakeJudgeService.

### Ngày 4–5

* Auth.
* Problem.
* TestCase.
* Django Admin.
* Problem detail.
* Bắt đầu Judge0 Spike.

Milestone Tuần 1:

```text
Admin tạo đề
→ Player login
→ Player xem được đề
```

## Tuần 2 — Submission và Match Foundation

### Đầu tuần

* Judge0 thật.
* Submission.
* Hidden tests.
* Verdict mapping.
* Error handling.

### Giữa tuần

* Submission UI.
* Integration tests.
* Judge offline handling.
* Gate 1.

### Cuối tuần

* Match.
* MatchPlayer.
* MatchProblem.
* PlayerProblemProgress.
* Create Room.
* Join Room.
* Gate 2.

Checkpoint giữa Tuần 2:

```text
A tạo phòng
→ B nhập mã
→ hai người xuất hiện trong cùng Match
```

## Tuần 3 — Playable Battle

* Waiting Room tối giản.
* Start Match.
* Freeze problems.
* Battle UI.
* Submit trong Match.
* Base score.
* First-solve `+1`.
* Timer.
* State endpoint.
* Polling.
* Result.

Checkpoint giữa Tuần 3:

```text
Hai player bắt đầu trận
→ submit
→ điểm thay đổi
→ timer chạy
```

Milestone cuối Tuần 3:

* Một trận hoàn chỉnh chạy được.

## Tuần 4 — Stabilization và Release

### Đầu tuần

* Deploy MVP.
* Fix integration.
* Refresh/re-entry.
* Error handling.
* Load test nhỏ.

### Giữa tuần

* Feature freeze.
* UI polish.
* Seed data.
* End-to-end testing.

### Cuối tuần

* Demo rehearsal.
* Slide.
* Question bank.
* Video backup.
* Final release.

Quyết định:

* Từ giữa Tuần 4 thực hiện feature freeze.
* Tuần 4 không dùng để bắt đầu xây core.
* Không thêm Energy hoặc Skills nếu core chưa ổn định.

---

# 32. Checkpoint và cơ chế cắt scope

Nếu Tuần 2 hoặc Tuần 3 trễ, cắt theo thứ tự:

1. Waiting Room UI tối giản.
2. Bỏ animation.
3. Bỏ Submission history trong Battle.
4. Bỏ custom input.
5. Bỏ rematch.
6. Bỏ profile.
7. Bỏ leaderboard.
8. Dùng số bài cố định cho demo nếu problem selection chưa ổn.
9. Giảm UI polish.

Không cắt:

* Judge.
* Hidden tests.
* Submit.
* Match.
* Score.
* First-solve nếu đã là rule Gameplay chính thức.
* Timer.
* Result.
* Server-authoritative state.

---

# 33. Phân công ba thành viên

## 33.1. Thành viên A — Backend và Database

Trách nhiệm chính:

* Django Models.
* Migration.
* Django Auth.
* Problem Bank.
* Django Admin.
* Match.
* Room.
* Constraints.
* Server validation.
* Database integrity.

Task đầu tiên:

```text
A-01: Viết Database Design V1.
A-02: Khởi tạo Django skeleton.
A-03: Tạo Problem và TestCase.
```

## 33.2. Thành viên B — Frontend và UX

Trách nhiệm chính:

* User Flow.
* Wireframe.
* Django Templates.
* HTML/CSS.
* Form.
* Lobby.
* Waiting Room.
* Battle UI.
* Polling.
* Result.
* Loading/error/disabled states.

Task đầu tiên:

```text
B-01: Vẽ User Flow và sáu wireframe.
B-02: Tạo base template và CSS structure.
B-03: Tạo Problem List và Problem Detail UI.
```

## 33.3. Thành viên C — Judge và Gameplay

Trách nhiệm chính:

* JudgeService.
* FakeJudgeService.
* Judge0.
* SubmissionService.
* Verdict.
* Hidden tests.
* ScoringService.
* First-solve.
* Timer logic.
* Winner.
* Automated tests.

Task đầu tiên:

```text
C-01: Viết Submit Flow và JudgeService interface.
C-02: Tạo FakeJudgeService.
C-03: Thực hiện Judge0 connectivity spike.
```

## 33.4. Trách nhiệm chung

Cả ba phải hiểu flow:

```text
Submit
→ Django View
→ SubmissionService
→ JudgeService
→ Judge0
→ lưu Submission
→ ScoringService
→ cập nhật MatchPlayer
→ frontend polling state
```

Không được có module chỉ một người hoặc chỉ Codex hiểu.

---

# 34. Cách làm song song mà không giẫm chân nhau

## 34.1. Mỗi task có một owner

Một task chỉ có một người chịu trách nhiệm chính.

Người khác là reviewer, không viết implementation song song vào cùng file.

Ví dụ:

| Task              | Owner | Reviewer |
| ----------------- | ----- | -------- |
| Problem model     | A     | C        |
| Problem detail UI | B     | A        |
| JudgeService      | C     | A        |
| Create Room       | A     | B        |
| Polling UI        | B     | C        |
| First-solve       | C     | A        |

## 34.2. Quyền sở hữu file theo sprint

Ví dụ:

### A

```text
problems/models.py
matches/models.py
admin.py
migrations/
```

### B

```text
templates/
static/
browser JavaScript
```

### C

```text
submissions/services/
gameplay/services/
tests/
```

Các file chung như:

* `settings.py`.
* Root `urls.py`.
* Shared service interfaces.

phải có owner tạm thời cho mỗi task.

## 34.3. Dùng interface và mock

FakeJudgeService giúp A và B không phải chờ C hoàn thành Judge0.

Interface Contract giúp B và A làm frontend/backend song song.

## 34.4. Merge nhỏ

* Không giữ branch một tuần.
* Pull request nên giải quyết một task.
* Merge trong ngày hoặc ngày hôm sau.
* Không tạo một pull request khổng lồ cho toàn bộ module.

---

# 35. Git workflow

## 35.1. Branch

Đơn giản:

```text
main
feature/*
fix/*
```

Ví dụ:

```text
feature/problem-bank
feature/judge-service
feature/create-room
feature/battle-ui
fix/double-score
```

Không push thẳng vào `main`.

`main` phải luôn chạy được.

## 35.2. Quy trình đầu ngày

```bash
git checkout main
git pull
git checkout -b feature/<task-name>
```

Nếu branch đã tồn tại:

```bash
git checkout feature/<task-name>
git rebase main
```

hoặc merge main theo workflow nhóm đã thống nhất.

## 35.3. Commit

Ví dụ:

```text
feat: add problem admin
feat: add room creation flow
fix: prevent duplicate score
test: add first solve tests
```

Commit phải nhỏ và có ý nghĩa.

## 35.4. Pull request

PR phải có:

* Mục tiêu.
* File thay đổi.
* Database/migration.
* Cách test.
* Screenshot nếu có UI.
* Rủi ro.
* Checklist.

Không merge khi:

* Code chưa chạy.
* Chưa có migration khi đổi model.
* Có conflict chưa hiểu.
* Thêm dependency chưa được thống nhất.
* Codex tạo code nhưng owner không giải thích được.
* Task chưa đạt acceptance criteria.

## 35.5. Review

* Ít nhất một người khác review.
* Reviewer phải chạy hoặc kiểm tra flow chính.
* Không review chỉ bằng cách nhìn diff nếu thay đổi ảnh hưởng database/gameplay.

---

# 36. Board quản lý công việc

Dùng GitHub Projects hoặc Trello.

Các cột:

```text
Backlog
Ready
In Progress
Review
Testing
Done
Blocked
```

Mỗi task phải có:

* ID.
* User story.
* Goal.
* Acceptance criteria.
* Owner.
* Reviewer.
* Estimate.
* Dependencies.
* Files dự kiến sửa.
* Manual test.
* Technical constraints.
* Out of scope.

Task nên kéo dài:

* Khoảng nửa ngày đến hai ngày.

Task kéo dài một tuần phải được chia nhỏ.

---

# 37. Definition of Ready

Task chỉ được chuyển sang `Ready` khi:

* Yêu cầu rõ.
* Có acceptance criteria.
* Gameplay liên quan đã chốt.
* Có wireframe nếu là UI.
* Biết data đọc/ghi.
* Biết route hoặc interface.
* Dependency sẵn sàng hoặc có mock.
* Không còn câu hỏi nghiệp vụ lớn.
* Không xung đột với task khác.
* Owner đã được chỉ định.

---

# 38. Definition of Done

Task chỉ được coi là Done khi:

* Đúng acceptance criteria.
* Code đã push.
* Có migration nếu đổi model.
* Test chính đã chạy.
* Không lộ secret.
* Không thêm công nghệ ngoài kế hoạch.
* PR được review.
* Merge vào `main`.
* Một thành viên khác kiểm tra được.
* Tài liệu liên quan được cập nhật.
* Không phá flow cũ.
* Có hướng dẫn manual test.

---

# 39. Quy tắc sử dụng Codex

Codex là development assistant, không phải PM tự do.

## 39.1. Prompt bắt buộc phải có

* Context.
* Goal.
* Scope.
* Allowed files.
* Functional requirements.
* Acceptance criteria.
* Technical constraints.
* Out of scope.
* Manual test.
* Required explanation.

## 39.2. Codex không được tự ý

* Đổi Django sang framework khác.
* Thêm Redis.
* Thêm WebSocket.
* Thêm React.
* Đổi SQLite.
* Thêm model ngoài Database Design.
* Thay gameplay.
* Đổi API contract.
* Refactor toàn bộ project.
* Thêm dependency.
* Thêm feature phụ.
* Tự quyết định số bài hoặc timer.
* Tự thay First-solve rule.

## 39.3. Sau mỗi task Codex phải trả lời

1. File đã sửa.
2. Flow request.
3. Database bị ảnh hưởng.
4. Migration.
5. Test đã thêm.
6. Cách test thủ công.
7. Rủi ro còn lại.
8. Phần nào nhóm phải hiểu trước khi merge.

Quy tắc:

> Không merge đoạn code mà không thành viên nào giải thích được.

---

# 40. Tài liệu quản trị dự án

Cấu trúc:

```text
docs/
├── 00-project-charter.md
├── 01-product-vision.md
├── 02-prd-v1.md
├── 03-gameplay-spec.md
├── 04-release-roadmap.md
├── 05-system-design.md
├── 06-database-design.md
├── 07-interface-contract.md
├── 08-ui-ux-spec.md
├── 09-setup-local.md
├── 10-development-workflow.md
├── 11-test-plan.md
├── 12-deployment-guide.md
├── 13-demo-script.md
├── 14-risk-register.md
└── 15-decision-log.md
```

Ngoài ra:

```text
README.md
GitHub Project Board
Figma wireframes
```

## 40.1. Trạng thái tài liệu

### Đã chốt hoặc có baseline

* Project Charter.
* Product Vision.
* PRD V1 theo Django.
* Gameplay Master/Gameplay Specification từ giai đoạn đầu.
* Release Roadmap V1–V4.
* Master Project Context.

### Chưa viết bản chính thức

* System Design V1.
* Database Design V1.
* Interface Contract.
* UI/UX Specification.
* Setup Local chính thức.
* Development Workflow chi tiết.
* Product Backlog chính thức.
* Test Plan đầy đủ.
* Deployment Guide.
* Demo Script.
* Risk Register file riêng.
* Decision Log file riêng.

## 40.2. Thứ tự tài liệu tiếp theo

```text
1. System Design V1
2. Database Design V1
3. Interface Contract
4. UI/UX Specification
5. Product Backlog
6. Setup Local
7. Development Workflow
8. Test Plan
9. Deployment Guide
10. Demo Script
```

Không cần dừng toàn bộ setup trong lúc viết tài liệu, nhưng không code diện rộng khi schema chưa chốt.

---

# 41. Test Plan baseline

## 41.1. Auth

* Register hợp lệ.
* Register trùng username.
* Login đúng.
* Login sai.
* Logout.
* Guest vào protected route.
* Session còn hoạt động sau refresh.

## 41.2. Problem Bank

* Admin tạo Problem.
* Admin tạo sample test.
* Admin tạo hidden test.
* Player thấy sample.
* Player không thấy hidden.
* Inactive Problem không được chọn.
* Points được lưu đúng.

## 41.3. Room

* Create Room.
* Room code hợp lệ.
* Join đúng mã.
* Join sai mã.
* Người thứ ba bị từ chối.
* User join hai lần.
* Host start thiếu người.
* Non-host start.
* Refresh Waiting Room.

## 41.4. Judge

* Accepted.
* Wrong Answer.
* Syntax Error.
* Runtime Error.
* Timeout.
* Output quá dài.
* Judge0 offline.
* Nhiều hidden test.
* Một hidden test fail.
* Network timeout.

## 41.5. Submission

* User không thuộc Match.
* Problem không thuộc Match.
* Match chưa Start.
* Match đã Finish.
* Submission sau timeout.
* Source code rỗng.
* Submission được lưu.

## 41.6. Scoring

* Accepted lần đầu.
* Accepted lần hai.
* Wrong Answer không cộng điểm.
* Base score đúng.
* First-solve `+1`.
* Người thứ hai chỉ nhận base score.
* Hai submission gần đồng thời.
* Judge hoàn thành sai thứ tự.
* `scoring_processed` chống chạy lại.
* Một bài không cộng hai lần.

## 41.7. Timer

* Remaining time đúng.
* Refresh không reset.
* Hết giờ chuyển Finished.
* Submit sau thời gian bị từ chối.
* Hai client thấy thời gian gần nhau.

## 41.8. Polling

* State đúng theo user.
* Không lộ source.
* Không lộ hidden tests.
* Dừng sau Finished.
* Tab hidden giảm polling nếu triển khai.
* Query không tăng theo số bài.
* Không ghi DB mỗi lần poll.

## 41.9. End-to-end

```text
Register
→ Login
→ Admin tạo đề
→ Player A tạo phòng
→ Player B join
→ Host start
→ Hai người nhận cùng bài
→ Submit
→ Judge
→ Score
→ First-solve
→ Timer hết
→ Result
```

---

# 42. Risk Register

| ID   | Rủi ro                               |   Mức độ | Trigger                             | Biện pháp                                                              |
| ---- | ------------------------------------ | -------: | ----------------------------------- | ---------------------------------------------------------------------- |
| R-01 | Judge0 chưa tích hợp đầu Tuần 2      | Critical | Không xử lý được verdict cơ bản     | Ưu tiên toàn nhóm, dùng FakeJudge để module khác tiếp tục              |
| R-02 | Judge0 rate limit hoặc lỗi mạng      |     High | Request bị từ chối hoặc timeout     | Retry có kiểm soát, external/self-host fallback                        |
| R-03 | Judge0 sandbox behavior khác dự kiến |     High | Timeout/output không ổn định        | Judge Spike sớm, test while True và output lớn                         |
| R-04 | Battle Core bị dồn vào Tuần 3        | Critical | Cuối Tuần 2 chưa có Room            | Kéo Match Foundation về Tuần 2                                         |
| R-05 | State endpoint N+1 query             |     High | Query tăng theo số bài              | Query audit, select_related/prefetch_related                           |
| R-06 | Polling gây lag                      |   Medium | Nhiều request chậm                  | Response nhỏ, giảm polling khi tab ẩn, dừng khi Finished               |
| R-07 | SQLite database locked               |   Medium | Lỗi ghi đồng thời                   | Không write trong polling, transaction ngắn, chuyển PostgreSQL nếu cần |
| R-08 | First-solve cộng hai lần             |     High | Hai Accepted gần nhau               | Transaction, constraint, idempotency, concurrency test                 |
| R-09 | Judge trả sai thứ tự                 |     High | Submission sau hoàn thành trước     | Dùng `received_at`, không dùng completion order                        |
| R-10 | Codex tạo code ngoài khả năng hiểu   | Critical | Owner không giải thích được         | Task nhỏ, review chéo, không merge                                     |
| R-11 | Scope tăng                           | Critical | Đề xuất Energy/UI phụ trong V1      | PRD freeze, Change Request                                             |
| R-12 | UI chiếm thời gian                   |     High | Core chưa chạy nhưng polish kéo dài | Textarea trước, layout cố định, animation sau                          |
| R-13 | Ghép module cuối kỳ                  |     High | Branch tồn tại lâu                  | Vertical slice, merge nhỏ, demo hàng tuần                              |
| R-14 | Deploy quá muộn                      |     High | Tuần 4 chưa từng deploy             | Deploy skeleton cuối Tuần 2/đầu Tuần 3                                 |
| R-15 | Tài liệu làm chậm code               |   Medium | Sau ngày 2 chưa có skeleton         | Time-box tài liệu hai ngày                                             |
| R-16 | Một thành viên bị block              |   Medium | Chờ Judge/API                       | Mock interface, task độc lập                                           |
| R-17 | Mất dữ liệu demo                     |   Medium | Database lỗi/reset                  | Seed command, backup                                                   |
| R-18 | Hội đồng hỏi sâu                     |     High | Nhóm không giải thích được          | Question Bank, review kiến thức                                        |
| R-19 | Azure credit bị tiêu hao sớm         |   Medium | Chạy tài nguyên không cần thiết     | Local trước, tắt tài nguyên khi không dùng                             |
| R-20 | Azure deployment phức tạp            |     High | App local chạy nhưng cloud fail     | Deploy skeleton sớm, deployment checklist                              |
| R-21 | Problem bị sửa khi Match active      |   Medium | Điểm/nội dung thay đổi              | Freeze MatchProblem, không sửa đề active                               |
| R-22 | Hidden tests bị lộ                   | Critical | Response chứa test hidden           | Test response, server-only access                                      |
| R-23 | Source code chạy trong Django        | Critical | Dùng exec/eval                      | Cấm tuyệt đối, Judge0 only                                             |

---

# 43. Azure Deployment Roadmap

## 43.1. Không dùng Azure quá sớm

Hai tuần đầu:

* Chạy local.
* Học Django.
* Xây Problem Bank.
* Xây Submission.
* Tích hợp Judge.

## 43.2. Deployment lần 1 — Skeleton

Thời điểm:

* Cuối Tuần 2 hoặc đầu Tuần 3.

Phạm vi:

* Health.
* Login.
* Problem page.
* Có thể chưa có full battle.

Mục đích:

* Kiểm tra environment variables.
* Kiểm tra static files.
* Kiểm tra allowed hosts.
* Kiểm tra migration.
* Kiểm tra mạng.
* Giảm rủi ro deploy cuối kỳ.

## 43.3. Deployment lần 2 — MVP

Thời điểm:

* Đầu Tuần 4.

Bao gồm:

* Auth.
* Problem Bank.
* Room.
* Battle.
* Judge.
* Result.

## 43.4. Deployment checklist

```text
□ Production environment variables
□ DEBUG=False
□ ALLOWED_HOSTS
□ Secret key
□ Database migration
□ Static files
□ Admin account
□ Seed problems
□ Judge endpoint
□ Health smoke test
□ Login smoke test
□ Submission smoke test
□ One complete match
□ Log inspection
□ Backup/restore plan
```

## 43.5. Azure service chưa chốt

Chưa có quyết định cuối cùng về:

* Azure App Service.
* Azure VM.
* Container deployment.
* Judge0 self-host location.

Quyết định phải dựa trên:

* Độ dễ triển khai.
* Chi phí credit.
* Judge0 requirement.
* Khả năng nhóm giải thích.
* Thời gian còn lại.

Không được tự chọn Kubernetes hoặc hệ thống phức tạp.

---

# 44. Demo và bảo vệ

## 44.1. Dữ liệu demo

Chuẩn bị:

* Hai tài khoản Player.
* Một tài khoản Admin.
* 3–5 bài ổn định.
* Code Accepted có sẵn.
* Code Wrong Answer có sẵn.
* Code Timeout có sẵn.
* Seed command.

## 44.2. Demo script

1. Admin mở Problem Bank.
2. Giới thiệu sample và hidden tests.
3. Player A đăng nhập và tạo phòng.
4. Player B nhập room code.
5. Host bắt đầu.
6. Cả hai thấy cùng danh sách bài.
7. Player A submit code đúng.
8. Judge trả Accepted.
9. Điểm cập nhật ở cả hai màn hình.
10. Giải thích First-solve `+1`.
11. Player B submit code sai hoặc đúng sau.
12. Timer tiếp tục chạy.
13. Match kết thúc.
14. Hệ thống hiển thị Result.
15. Nhóm trình bày roadmap Energy và Skills.

## 44.3. Phương án dự phòng

* Video demo.
* Screenshot.
* Local version.
* Seed database.
* Code mẫu.
* FakeJudge chỉ dùng trong tình huống khẩn cấp và phải nói rõ nếu demo không dùng Judge thật.

## 44.4. Question Bank

Nhóm phải chuẩn bị trả lời:

### Product

* Vấn đề là gì?
* Khác LeetCode ở đâu?
* Vì sao Energy và Skills chưa có trong V1?

### Technical

* Vì sao chọn Django?
* Vì sao SQLite?
* Vì sao polling?
* Judge0 hoạt động thế nào?
* Hidden tests được bảo vệ ra sao?
* First-solve xử lý race thế nào?
* Timer do ai quyết định?

### Project management

* Nhóm chia việc thế nào?
* Codex được kiểm soát ra sao?
* Vì sao bỏ FastAPI architecture?
* Rủi ro lớn nhất là gì?
* Azure được sử dụng thế nào?

---

# 45. Tiêu chí thành công của V1

V1 được coi là hoàn thành khi:

```text
Đăng ký
→ Đăng nhập
→ Admin tạo Problem/TestCase
→ Tạo phòng
→ Join phòng
→ Start Match
→ Nhận cùng MatchProblem
→ Submit Python
→ Judge hidden tests
→ Lưu Submission
→ Cộng base score
→ First-solve +1
→ Không duplicate score
→ Polling state
→ Timer phía server
→ Refresh quay lại trận
→ Match Finished
→ Winner đúng
→ Result
→ Deploy thành công
```

Ngoài việc chạy được, nhóm phải:

* Giải thích được kiến trúc.
* Giải thích được database.
* Giải thích được request flow.
* Giải thích được Judge0.
* Giải thích được hidden tests.
* Giải thích được timer.
* Giải thích được scoring.
* Giải thích được First-solve.
* Giải thích được lý do chọn Django.
* Trình bày được roadmap Energy, Skills, Defense và Minigames.
* Chứng minh CodeHehe không chỉ là LeetCode clone.
* Demo lặp lại được nhiều lần.

---

# 46. Quyết định chính thức đang có hiệu lực

1. Tên dự án là CodeHehe.
2. Đội có ba sinh viên năm hai AI.
3. Thời gian V1 khoảng bốn tuần.
4. V1 dùng Python only.
5. V1 là Coding Battle Core.
6. Energy và Skills không bị bỏ, chỉ lùi phiên bản.
7. V1 dùng Django monolith.
8. V1 dùng Django Templates.
9. V1 dùng Vanilla JavaScript.
10. V1 dùng SQLite.
11. V1 dùng Django Auth và Session.
12. V1 dùng Django Admin.
13. V1 dùng Polling thay WebSocket.
14. V1 dùng Room Code thay automatic matchmaking.
15. V1 dùng Judge0 để chạy code.
16. Không dùng `exec()` hoặc `eval()`.
17. Hidden tests không được gửi về frontend.
18. Server là nguồn sự thật.
19. Timer do server quyết định.
20. Match problems phải được frozen khi Start.
21. Mỗi người có progression độc lập.
22. Một bài chỉ cộng base score một lần/người/trận.
23. First-solve `+1` nằm trong V1.
24. First-solve dựa trên thời điểm server nhận submission.
25. Không dùng Judge completion order cho First-solve.
26. Scoring phải idempotent.
27. Phải chống duplicate score.
28. Judge0 Spike bắt đầu cuối Tuần 1.
29. Judge thật phải chạy chậm nhất trong Tuần 2.
30. FakeJudgeService phải tồn tại.
31. Match Foundation được kéo về cuối Tuần 2.
32. Playable MVP phải có cuối Tuần 3.
33. Tuần 4 dành cho hardening và release.
34. Feature freeze từ giữa Tuần 4.
35. Deploy skeleton cuối Tuần 2 hoặc đầu Tuần 3.
36. Deploy MVP đầu Tuần 4.
37. Không dùng Azure ngay ngày đầu.
38. Không dùng Redis trong V1.
39. Không dùng PostgreSQL trong baseline V1.
40. Không dùng React trong V1.
41. Không dùng FastAPI trong V1.
42. Không dùng Docker bắt buộc cho local V1.
43. Không dùng WSL bắt buộc cho local V1.
44. Không dùng Node.js trong V1.
45. System Design và Database Design phải time-box trong hai ngày.
46. Tài liệu không được trở thành blocker hành chính.
47. Không code diện rộng trước khi schema và flow chính được chốt.
48. Mỗi task có một owner.
49. Mỗi feature dùng branch riêng.
50. Không push thẳng vào main.
51. PR phải được review.
52. Không merge code mà nhóm không giải thích được.
53. Codex chỉ làm task nhỏ có scope rõ.
54. Không để Codex tự thêm công nghệ hoặc model.
55. Polling Playing khoảng một giây.
56. Waiting Room có thể polling khoảng hai giây.
57. Polling dừng khi Match Finished.
58. State endpoint phải nhẹ.
59. State endpoint không được write DB.
60. Không thêm cache trước khi có bằng chứng cần thiết.
61. Energy: giải bài nhận 1.
62. Energy tối đa 3.
63. Hint tốn 1 Energy.
64. Defense gồm Cleanse, Reflect và Shield.
65. Minigames gồm Flappy Bird, Dinosaur, Math và Typing.
66. Skip chưa chốt và không nằm trong V1.
67. Elo nằm ở phiên bản sau.
68. PostgreSQL, Redis và WebSocket có thể được thêm ở V4 hoặc khi nhu cầu thực tế xuất hiện.
69. Django có thể được giữ làm backend dài hạn.
70. FastAPI chỉ cân nhắc về sau nếu cần tách service có lý do rõ ràng.

---

# 47. Các điểm còn cần xác nhận trong tài liệu tiếp theo

Các điểm sau chưa được chốt tuyệt đối hoặc từng có nhiều con số minh họa khác nhau:

## 47.1. Số bài mỗi trận

* Gameplay ban đầu: khoảng 4–5 bài.
* Một số ví dụ Django: 3 bài.

Cần đọc lại Gameplay Specification chính thức và ghi một giá trị baseline.

## 47.2. Thời lượng trận

* Ví dụ từng sử dụng: 15 phút.
* Chưa có xác nhận cuối rõ ràng trong toàn bộ quyết định đã tổng hợp.

Phải chốt trong Gameplay Specification.

## 47.3. Tie-break

* First-solve đã chốt.
* Quy tắc khi tổng điểm bằng nhau phải được ghi rõ trong Gameplay Specification.
* Không để developer tự chọn.

## 47.4. Cách chọn bài

Cần chốt:

* Random trong tập active.
* Theo blueprint.
* Theo admin.
* Danh sách cố định cho demo.

Dù chọn cách nào, MatchProblem phải frozen.

## 47.5. Judge0 hosting

Chưa chốt:

* External endpoint.
* Self-host Azure VM.
* VPS khác.

Phải quyết định sau Judge Spike.

## 47.6. Phiên bản dependency

Chưa chốt chính xác:

* Python.
* Django.
* Requests/http client.
* Judge0.
* Production server.

## 47.7. Azure service

Chưa chốt:

* App Service.
* VM.
* Container.
* Database service.

## 47.8. Problem versioning

V1 không dùng full ProblemVersion.

Cần chốt trong Database Design:

* Snapshot điểm.
* Có snapshot nội dung hay không.
* Quy tắc khóa chỉnh sửa đề active.

## 47.9. First-solve schema

Cần Database Design quyết định:

* Lưu `first_solver_player_id` ở MatchProblem.
* Lưu qua record riêng.
* Cách transaction trên SQLite.
* Cách xử lý pending submission trước.

---

# 48. Việc phải làm ngay sau tài liệu này

## Ngày 1–2

### Team

* Tạo GitHub repository.
* Tạo GitHub Project.
* Đưa tài liệu này vào `docs/`.
* Chốt Python/Django version.
* Cài môi trường ba máy.
* Chốt số bài và thời lượng Match.

### Thành viên A

* Viết Database Design V1.
* Vẽ ERD.
* Chốt First-solve schema.

### Thành viên B

* Viết UI Flow.
* Vẽ sáu wireframe.
* Chốt Battle layout.

### Thành viên C

* Viết JudgeService interface.
* Viết Submit Flow.
* Chuẩn bị Judge0 Spike.

## Ngày 3

* Khởi tạo Django.
* Health endpoint.
* Base template.
* FakeJudgeService.
* Merge các task nhỏ.

## Ngày 4–5

* Auth.
* Problem Bank.
* Admin.
* Problem Detail.
* Judge0 connectivity.

---

# 49. Baseline cuối cùng

```text
Project:
CodeHehe

Competition:
SOFTCON cấp trường

Team:
3 sinh viên năm hai chuyên ngành AI

Duration:
Khoảng 4 tuần

V1 Product:
Coding Battle Core

V1 Technology:
Django Monolith
SQLite
Django Templates
Vanilla JavaScript
Polling
Django Auth
Django Admin
Judge0
Python only

V1 Gameplay:
1v1
Same frozen problem list
Independent progression
Hidden tests
Base score
First-solve +1
Server timer
Near-realtime progress
Winner/result

Future Gameplay:
Energy
Max Energy = 3
Solve = +1 Energy
Hint = -1 Energy
Attack Skills
Cleanse
Reflect
Shield
Minigames
Elo
Rank
Matchmaking

Delivery Gates:
Gate 1 — Judge + Submission trong Tuần 2
Gate 2 — Room trong cuối Tuần 2
Gate 3 — Playable MVP trong cuối Tuần 3
Feature Freeze — Giữa Tuần 4
Final Release — Cuối Tuần 4

Cloud:
Azure Student
100 USD credit
12 tháng
Không dùng quá sớm
Deploy skeleton cuối Tuần 2/đầu Tuần 3
Deploy MVP đầu Tuần 4
```

---

# 50. Tuyên bố quản trị dự án

Dự án CodeHehe sẽ không được triển khai theo cách:

```text
Có ý tưởng
→ prompt Codex xây toàn bộ
→ cuối kỳ mới ghép và học lại
```

Quy trình chính thức:

```text
Product baseline
→ Gameplay rules
→ System Design
→ Database Design
→ Interface Contract
→ Wireframe
→ Small backlog tasks
→ Local setup
→ Vertical slices
→ Continuous integration
→ Testing
→ Early deployment
→ Feature freeze
→ Demo rehearsal
```

Tiêu chuẩn cao nhất của dự án không phải số lượng công nghệ hoặc số lượng tính năng.

Tiêu chuẩn cao nhất là:

> Sản phẩm chạy được, nhóm hiểu được, sửa được, kiểm thử được, triển khai được và bảo vệ được trước hội đồng, đồng thời vẫn giữ nền tảng rõ ràng để phát triển Energy, Skills và gameplay dài hạn.
