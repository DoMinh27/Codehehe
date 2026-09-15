# Gameplay Classic v3.2

## Luật trận

- Hai người chơi trong một phòng; host bắt đầu khi đủ 2/2
- Thời lượng mặc định: 300 giây
- Bộ đề snapshot khi bắt đầu: 2 Easy, 1 Medium và 1 Hard
- Điểm cơ bản theo độ khó: Easy 1, Medium 2, Hard 3
- Người giải AC đầu tiên của một bài nhận thêm 1 điểm, 1 Energy và một lượt Kỹ
  năng ngẫu nhiên theo snapshot trận
- Energy tối đa là 3
- Trận kết thúc khi hết giờ, cả hai giải hết bài hoặc một người đầu hàng
- Kết quả dựa trên điểm, trừ trường hợp đầu hàng xác định trực tiếp người thắng

`Match.ruleset_version` hiện là `v3.2`. `rules_snapshot`, `MatchProblem` và
`MatchSkill` giữ luật, đề, test và chính sách Kỹ năng ổn định trong suốt trận.
Trận v3.1 cũ vẫn đọc được nhưng không tự nhận Khiên.

## Bảy Kỹ năng

| Kỹ năng | Mục tiêu | Giá | Tác động |
|---|---|---:|---|
| Đảo chiều code | Đối thủ | 1 Energy | 35 giây |
| Che mờ đề | Đối thủ | 1 Energy | 35 giây |
| Trừ thời gian | Đối thủ | 1 Energy | Trừ 60 giây |
| Thử thách gõ chữ | Đối thủ | 1 Energy | Tối đa 20 giây |
| Thanh tẩy | Bản thân | 1 Energy | Gỡ một hiệu ứng bất lợi mới nhất |
| Tước đoạt | Đối thủ | 2 Energy | Lấy ngẫu nhiên một lượt Kỹ năng, trừ Tước đoạt |
| Khiên | Bản thân | 1 Energy | Chặn một đòn hoặc hết hạn sau 45 giây |

Thanh tẩy không hoàn lại thời gian đã bị trừ. Khiên chặn Kỹ năng tấn công tiếp
theo sau khi đòn đã vượt qua validation; người tấn công vẫn mất Energy và lượt
Kỹ năng. Khiên là hiệu ứng có lợi nên không bị Thanh tẩy gỡ.

## Trình bày và riêng tư trong Battle

- Toolbar chia Kỹ năng phòng thủ và tấn công bằng vị trí icon, không công khai
  inventory của đối thủ
- Tooltip dùng tên, mô tả, mục tiêu, giá, kiểu tác động và số lượt theo một format
  thống nhất
- Khiên chỉ xuất hiện trong active effects của chủ sở hữu; đối thủ chỉ biết khi
  đòn của họ thực sự bị chặn
- Thanh tẩy chỉ phản hồi cho người sử dụng
- Combat notification không chứa username, player ID hoặc target name
- Các hiệu ứng bất lợi chỉ xuất hiện với người đang chịu
- Timeline sau trận vẫn giữ actor, target và outcome đầy đủ để participant hoặc
  staff được phép có thể kiểm tra diễn biến

## Chấm bài và hoàn tất

Run Code không tạo Submission và không tính activity. Submit hợp lệ tạo
Submission, gọi Judge0, cập nhật progress/score/reward theo transaction và ghi
ngày hoạt động. Verdict trả muộn không được thay đổi trận đã kết thúc sai quy
tắc. Sweeper xử lý trận quá hạn và submission pending quá ngưỡng.

AI Review chỉ chạy theo yêu cầu sau trận, đọc bài nộp của người yêu cầu và không
tham gia vào scoring, winner hoặc Fair Play.
