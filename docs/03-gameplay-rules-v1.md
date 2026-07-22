# TÀI LIỆU 3 — GAMEPLAY RULES V1

**Tên file đề xuất:** `03-gameplay-rules-v1.md`

## 1. Mục tiêu gameplay V1

V1 phải chứng minh được rằng CodeHehe là một coding battle trực tiếp, không chỉ là website giải bài cá nhân.

Gameplay V1 tập trung vào:

* Cạnh tranh điểm số.
* Tốc độ giải bài.
* First-solve.
* Theo dõi tiến độ đối thủ.
* Giới hạn thời gian.

Energy và Skills chưa được kích hoạt trong V1 nhưng kiến trúc phải chuẩn bị đường nâng cấp.

---

## 2. Thành phần trận đấu

* Số người: 2.
* Hình thức: 1v1.
* Ngôn ngữ: Python.
* Runtime chính thức: Python 3.12.
* Số bài: 4.
* Thời gian: 15 phút.
* Hai bài đầu: Easy.
* Hai bài sau: Medium.
* Hard Problem không bắt buộc trong V1.
* Hai người nhận cùng danh sách bài.
* Mỗi người giải bài theo thứ tự tùy chọn.
* Không có chat.
* Không có spectator.
* Không có automatic matchmaking.

---

## 3. Bắt đầu trận

1. Player A tạo phòng và trở thành host.
2. Player B nhập mã phòng.
3. Phòng đạt đủ hai người.
4. Host nhấn Start.
5. Server chọn 4 Problem active theo cấu hình.
6. Server tạo MatchProblem và snapshot điểm.
7. Server đặt:

   * `status = PLAYING`.
   * `started_at`.
   * `ends_at = started_at + 15 phút`.
8. Hai người được chuyển tới Battle page.

Host không thể Start khi:

* Chỉ có một người.
* Match đã Start.
* Match đã Finished.
* Problem set không đủ 4 bài hợp lệ.

---

## 4. Quy tắc giải bài

* Player có thể mở bất kỳ bài nào trong danh sách.
* Không bắt buộc giải theo thứ tự.
* Progression của hai người độc lập.
* Việc một người giải xong không làm khóa hoặc mở bài của người kia.
* Player có thể submit nhiều lần.
* Submit sai không bị trừ điểm.
* Một bài chỉ tính điểm ở lần Accepted đầu tiên.
* Không có giới hạn số lần submit trong V1.
* Không có Run Custom Input trong phạm vi bắt buộc V1.

---

## 5. Chấm bài

Mỗi Submission được chấm bằng:

* Source code Python.
* Hidden tests.
* Time limit.
* Expected output.

Các kết quả:

* Accepted.
* Wrong Answer.
* Compilation Error.
* Runtime Error.
* Time Limit Exceeded.
* Internal Error.

Sample tests chỉ để người chơi hiểu đề, không quyết định Accepted chính thức.

---

## 6. Quy tắc thời gian

* Mỗi trận kéo dài 15 phút.
* Server là nguồn thời gian chính.
* Client chỉ hiển thị countdown.
* Refresh không reset timer.
* Disconnect không dừng timer.
* Submission được nhận sau `ends_at` bị từ chối.
* Submission được nhận trước `ends_at` vẫn được xử lý dù Judge0 hoàn thành sau giờ kết thúc.
* Match chỉ được finalize sau khi các Submission hợp lệ được nhận trước deadline đã có kết quả hoặc được xử lý theo timeout nội bộ.

---

## 7. Quy tắc điểm

## 7.1. Base score

Mặc định:

| Độ khó | Base score |
| ------ | ---------: |
| Easy   |          1 |
| Medium |          2 |
| Hard   |          3 |

Trong V1, Match có:

* 2 bài Easy.
* 2 bài Medium.

Tổng base score mặc định tối đa:

```text
1 + 1 + 2 + 2 = 6 điểm
```

## 7.2. First-solve bonus

* Mỗi bài có First-solve bonus `+1`.
* Người Accepted bài trước nhận bonus.
* Mỗi bài chỉ có một First-solver.
* Tổng First-solve bonus tối đa của một người là 4 nếu người đó giải trước toàn bộ bài.

Tổng điểm tối đa mặc định:

```text
Base score 6
+ First-solve 4
= 10 điểm
```

## 7.3. Xác định First-solve

First-solve được xác định theo:

```text
received_at của các Submission có verdict ACCEPTED
```

Không dùng:

* Judge completion time.
* Thời điểm frontend hiển thị kết quả.
* Thời điểm request response hoàn thành.

Ví dụ:

```text
A submit lúc 10:00:01
B submit lúc 10:00:03

Judge xử lý B trước
Judge xử lý A sau

Nếu cả hai Accepted:
A là First-solver.
```

Nếu A submit trước nhưng Wrong Answer, B Accepted sau:

* B là First-solver.

Nếu có Submission đến trước đang pending:

* Backend chưa được finalize First-solve cho submission đến sau cho đến khi biết kết quả các submission đến trước có khả năng cạnh tranh.
* Có thể hiển thị base score trước.
* First-solve được finalize khi thứ tự Accepted được xác định an toàn.

---

## 8. Quy tắc kết thúc

Match kết thúc khi:

### Trường hợp 1 — Hết thời gian

* Server time đạt `ends_at`.
* Không nhận submission mới.
* Các submission hợp lệ đã nhận trước deadline được hoàn tất xử lý.
* Server tính kết quả.

### Trường hợp 2 — Cả hai giải toàn bộ bài

* Cả hai Player Accepted cả 4 bài.
* Match có thể kết thúc sớm.
* Không cần chờ hết 15 phút.

### Trường hợp chỉ một người giải hết bài

* Match tiếp tục.
* Player còn lại được thi đấu tới hết thời gian hoặc tới khi cũng giải hết bài.

---

## 9. Xác định người thắng

Áp dụng theo thứ tự:

### Bước 1 — Tổng điểm

Người có tổng điểm cao hơn thắng.

### Bước 2 — Hòa

Nếu hai Player bằng điểm, Match có kết quả Draw. V1 không dùng số bài đã giải hoặc thời điểm đạt điểm cuối cùng làm tie-break.

---

## 10. Disconnect và refresh

* Refresh được phép.
* Player có thể đăng nhập lại và trở về Match.
* Timer tiếp tục.
* Score được đọc từ server.
* Source code chưa submit có thể mất nếu chưa có autosave; autosave không phải yêu cầu bắt buộc V1.
* Không xử thua tự động chỉ vì disconnect trong V1.
* Không có pause.

---

## 11. Hành vi bị cấm

* Frontend tự cộng điểm.
* Frontend tự xác nhận Accepted.
* Frontend nhận hidden tests.
* Chạy source code trong Django.
* Thay đổi Problem list giữa trận.
* Admin sửa nội dung hoặc điểm của Problem đang được dùng trong Match active.
* Cộng điểm nhiều lần cho cùng bài.
* Cộng First-solve cho cả hai Player.
* Reset timer khi refresh.
* Cho người thứ ba join.

---

## 12. Gameplay chưa có trong V1

### Energy

* Solve mới: `+1 Energy`.
* Tối đa: `3 Energy`.

### Hint

* Dùng một Hint: `-1 Energy`.

### Defense

* Cleanse.
* Reflect.
* Shield.

### Minigames

* Flappy Bird.
* Dinosaur.
* Math.
* Typing.

### Skip

* Chưa chốt rule.
* Không triển khai V1.
* Cần nghiên cứu để không phá frozen list và fairness.

### Elo

* Không triển khai V1.
* Thuộc Competitive System về sau.

---
