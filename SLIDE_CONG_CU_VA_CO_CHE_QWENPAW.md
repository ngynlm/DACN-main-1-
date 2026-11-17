

## Slide 3 — Công nghệ chính của dự án
“Backend Python đảm nhiệm API và phần điều phối. Console dùng React và
TypeScript, được Vite build thành tài nguyên web. AgentScope cung cấp nền tảng
agent mà QwenPaw mở rộng. Các thư viện provider giúp kết nối model; pytest và
Vitest kiểm tra mã; Docker và Tauri phục vụ đóng gói theo hình thức triển
khai.”

## Slide 4 — Kiến trúc tổng thể: Các lớp phối hợp với nhau

1. Tạo slide ngang 16:9. Chia nội dung thành ba dải ngang: **Tiếp nhận yêu
   cầu**, **Agent xử lý**, **Trả kết quả**.
2. Ở dải trên, đặt năm khối chữ nhật bo góc từ trái sang phải:
   **Người dùng → Console → FastAPI API → Runtime → AgentBuilder**.
3. Đặt khối **QwenPaw Agent** ở giữa slide, dưới `AgentBuilder`. Nối
   `AgentBuilder` xuống agent bằng mũi tên một chiều, ghi nhãn **“lắp model,
   prompt, context và toolkit”**.
4. Đặt khối **Model Factory / Provider** bên phải agent và khối
   **LLM cloud / local** bên phải provider. Nối theo thứ tự:
   **Agent → Model Factory / Provider → LLM**. Ghi nhãn trên mũi tên từ agent:
   **“prompt + context + tool schema”**.
5. Vẽ mũi tên quay về từ **LLM tới Agent**, ghi:
   **“phản hồi: văn bản hoặc yêu cầu tool_call”**. Hai mũi tên ngược chiều
   này biểu thị trao đổi request/response; nếu model trả tool_call, agent
   tiếp tục điều phối thay vì đưa nội dung đó ngay cho người dùng.
6. Bên dưới agent, đặt khối **Tool Guard / Approval** rồi khối
   **Tool thực thi**. Vẽ **Agent → Tool Guard → Tool** và ghi trên mũi tên
   đầu tiên **“yêu cầu gọi tool”**. Vẽ mũi tên từ **Tool về Agent**, ghi
   **“kết quả tool”**. Đây là vòng trao đổi nhiều lượt giữa agent và tool.
7. Từ Tool Guard có thể thêm ba nhánh nhỏ:
   - `ALLOW` → tiếp tục tới Tool.
   - `ASK` → khối **Người dùng duyệt**; sau khi duyệt mới tiếp tục, nếu từ
     chối thì trả thông báo về agent.
   - `DENY` → khối **Bị chặn**, rồi trả kết quả từ chối về agent.
8. Ở dải dưới cùng, vẽ **Agent → Runtime / Executor → SSE stream → Console
   → Người dùng**. Ghi chú **“SSE: phản hồi/sự kiện được gửi dần”**.
9. Dùng màu nhất quán: giao diện màu xanh dương, backend/runtime màu tím,
   agent/model màu xanh lá, tools màu cam, bảo mật màu đỏ nhạt. Dùng mũi tên
   liền cho luồng chính; mũi tên cong quay lại để biểu thị vòng lặp.

#### Cách giải thích mũi tên hai chiều

- **Agent ↔ Model:** agent gửi request; model trả nội dung hoặc yêu cầu gọi
  tool. Nếu có tool_call, agent có thể gọi tool rồi gửi kết quả trở lại model
  trong request tiếp theo. Vì vậy đây là vòng trao đổi có thể lặp, không nhất
  thiết chỉ một lần.
- **Agent ↔ Tool:** chính xác hơn, agent gửi yêu cầu gọi tool; tool chạy sau
  bước kiểm tra quyền; kết quả được trả lại agent. Model thường là bên đề xuất
  tool_call, còn agent/runtime điều phối việc thực thi.
- Nếu vẽ mũi tên hai đầu cho gọn, hãy ghi rõ nhãn trên từng chiều. Không nên
  để một mũi tên hai chiều không chú thích vì sẽ khó phân biệt request, kết
  quả model và kết quả tool.
- **AgentBuilder không phải một model khác**: nó chỉ tạo/lắp ghép agent cùng
  các phụ thuộc cần thiết trước khi thực thi.

### Lời thuyết trình

“Đây là kiến trúc ở mức khái niệm. Người dùng không gọi model trực tiếp từ
giao diện. Request đi qua API và runtime; builder tạo agent với model, prompt,
ngữ cảnh và công cụ. Agent trao đổi với model, có thể gọi tool, sau đó runtime
chuyển sự kiện phản hồi về giao diện.”

## Slide 5 — Backend khởi động và phục vụ giao diện như thế nào?

### Lời thuyết trình

“Lệnh CLI là điểm khởi động. Uvicorn chạy ứng dụng ASGI FastAPI; FastAPI đăng
ký các router API và khởi tạo dịch vụ trong lifespan. Frontend được build
trước, sau đó ứng dụng có thể phục vụ giao diện cùng backend. Địa chỉ loopback
giúp truy cập trên máy cục bộ; nếu bind ra mạng thì cần chú ý xác thực và
phạm vi truy cập.”

## Slide 6 — Bắt đầu một lượt chat: Từ giao diện tới API

### Lời thuyết trình

“Frontend không chứa khóa API model và không tự gọi model. Nó gọi API của
QwenPaw. Router phía backend xác định workspace và phiên chat, xử lý thông tin
đăng ký chat rồi gửi tác vụ sang lớp quản lý quá trình chạy. Các channel khác
có điểm nhận riêng nhưng thường chuyển dữ liệu sang cấu trúc yêu cầu agent
chung.”
## Slide 7 — Runtime: Bộ điều phối vòng đời yêu cầu

### Lời thuyết trình

“Runtime là nơi điều phối toàn bộ lượt chạy chứ không phải nơi model suy
luận. Nó chuẩn hóa đầu vào, chạy hook, có thể xử lý slash command trước khi
dựng agent, rồi chuyển sang builder và executor. Sau khi agent trả lời,
runtime chạy các xử lý hậu kỳ và kết thúc stream. Nếu có lỗi hoặc người dùng
hủy tác vụ, runtime phát trạng thái tương ứng và xử lý lưu trạng thái cần
thiết.”
## Slide 8 — AgentBuilder lắp ghép một agent cho mỗi yêu cầu

### Lời thuyết trình

“AgentBuilder tách việc dựng agent khỏi lớp agent. Nhờ đó agent không phải
tự biết cách đọc provider hay tạo tool. Builder thu thập các phụ thuộc, chọn
toolkit áp dụng cho yêu cầu rồi truyền model, system prompt và cấu hình vào
QwenPawAgent. Cách tổ chức này giúp các phần có ranh giới rõ hơn và dễ thay
đổi độc lập.”

## Slide 9 — Model Factory và Provider: Cầu nối tới LLM
### Lời thuyết trình

“QwenPaw không nhất thiết huấn luyện model khi chạy. Model factory chọn model
đã cấu hình, tìm provider tương ứng và tạo client. Formatter xử lý khác biệt
định dạng giữa các giao thức. Các wrapper bổ sung hành vi vận hành như ghi
nhận token, thử lại, giới hạn tốc độ hoặc chuyển model dự phòng nếu được cấu
hình.”

## Slide 10 — Agent trả lời: Vòng lặp ReAct và gọi model

### Lời thuyết trình

“Đây là điểm khác nhau giữa chatbot một lượt và agent có công cụ. Model đưa
ra yêu cầu gọi tool; ứng dụng mới là bên chạy hàm thật. Kết quả thực thi được
đưa ngược lại cho agent để model có thể phân tích tiếp. Một câu trả lời vì
vậy có thể phát sinh nhiều lần gọi model.”

## Slide 11 — Tools, Skills, Plugins và MCP

### Lời thuyết trình

“Các khái niệm này không đồng nghĩa. Tool là hành động chạy được. Skill thường
là hướng dẫn để agent thực hiện một loại tác vụ, có thể chỉ dẫn dùng một hay
nhiều tool. Plugin là cơ chế mở rộng. MCP là một chuẩn kết nối tới công cụ
hoặc dữ liệu bên ngoài. Builder và registry quyết định công cụ nào được đưa
vào toolkit.”

## Slide 12 — An toàn khi agent sử dụng công cụ

### Lời thuyết trình

“Model không được mặc nhiên quyền thực thi mọi yêu cầu. Trước khi chạy,
tool call đi qua lớp kiểm tra quyền và chính sách. Một số thao tác có thể
chạy, bị từ chối hoặc chờ người dùng phê duyệt. Tính năng sandbox và scanner
bổ sung lớp bảo vệ. Khi triển khai, vẫn cần cấu hình quyền hệ điều hành,
authentication và mạng phù hợp.”

## Slide 13 — Session, Context và Memory: Ba khái niệm khác nhau
### Lời thuyết trình

“Lịch sử chat, đầu vào thực sự của model và bộ nhớ dài hạn không phải một
thứ. Một session có thể có lịch sử dài, nhưng request gửi tới model có thể chỉ
chứa phần context được lựa chọn hoặc nén. Memory là khả năng lưu và tìm lại
thông tin khi cần. ReMe là backend mà dự án tích hợp cho một phần chức năng
bộ nhớ.”
## Slide 14 — Streaming, Channel và tác vụ định kỳ
### Lời thuyết trình

“Streaming cải thiện trải nghiệm vì người dùng có thể nhận sự kiện trong lúc
agent đang chạy, thay vì đợi toàn bộ phản hồi. Channel giúp cùng agent có thể
phục vụ nhiều nơi giao tiếp. Với tác vụ định kỳ, bộ lập lịch của ứng dụng
chịu trách nhiệm lưu lịch và kích hoạt job; model có thể tham gia xử lý công
việc nhưng không phải thành phần giữ giờ.”

