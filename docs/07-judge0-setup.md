# Judge0 setup

Judge0 là thành phần duy nhất được phép thực thi code Python do người chơi gửi.
Không dùng `exec` hoặc `eval` trong tiến trình Django.

## Các mô hình kết nối

- Local có thể dùng Judge0 trên cùng máy, trong Docker hoặc một endpoint
  Judge0-compatible bên ngoài
- Production hiện chạy Django và Judge0 trên cùng Ubuntu 22.04 Azure VM;
  Django gọi `http://127.0.0.1:2358`
- Port `2358` không được mở trong NSG hoặc công khai qua Nginx
- Nếu endpoint yêu cầu token, đặt `JUDGE0_API_KEY`; Judge0 CE nội bộ hiện để trống

Trong `.env` không được commit:

```text
JUDGE0_BASE_URL=http://127.0.0.1:2358
JUDGE0_API_KEY=
READINESS_CHECK_JUDGE0=True
```

Với endpoint ngoài, thay `JUDGE0_BASE_URL` và key theo nhà cung cấp. Không đưa
key vào lệnh shell, log, tài liệu hoặc frontend.

## Runtime Python

- Django được phát triển/test local bằng Python 3.12
- Production Ubuntu 22.04 hiện chạy Django bằng Python 3.10
- Submission sử dụng Judge0 language ID `71`, tương ứng Python 3.8.1 trong
  Judge0 CE đang dùng

Vì runtime submission có thể cũ hơn runtime Django, starter code, reference
solution và test data không được phụ thuộc cú pháp Python mới hơn môi trường
Judge0.

## Kiểm tra kết nối

Chạy từ đúng virtual environment và cùng bộ biến môi trường với Django:

```powershell
python manage.py judge0_spike
```

Trên production:

```bash
sudo -u codehehe bash -c '
  set -a
  source /etc/codehehe/codehehe.env
  set +a
  cd /opt/codehehe/app
  /opt/codehehe/venv/bin/python manage.py judge0_spike
'
```

Kết quả mong đợi theo thứ tự là `ACCEPTED`, `WRONG_ANSWER` và
`RUNTIME_ERROR`. Command chỉ gửi bộ input/output kiểm tra đã biết, không dùng
hidden test production.

Xác nhận Judge0 chỉ lắng nghe loopback:

```bash
sudo ss -ltnp | grep ':2358'
```

Output phải là `127.0.0.1:2358` hoặc `[::1]:2358`, không phải
`0.0.0.0:2358`.

## Khi có lỗi

- Kiểm tra container/service Judge0 và port loopback trước
- Chạy `judge0_spike` bằng user `codehehe` để loại trừ khác biệt environment
- Kiểm tra `journalctl -u codehehe` và Operations Dashboard nhưng không sao chép
  token hoặc payload chứa source vào báo cáo công khai
- Readiness có thể báo lỗi khi `READINESS_CHECK_JUDGE0=True`; tắt kiểm tra chỉ
  cho chẩn đoán có chủ đích, không dùng để che sự cố production
