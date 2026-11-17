import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Award,
  BookMarked,
  BookOpen,
  CalendarCheck,
  ChartNoAxesCombined,
  CheckCircle2,
  ClipboardList,
  GraduationCap,
  Lightbulb,
  MessageCircleQuestion,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import {
  learningTutorApi,
  type LearningHistoryItem,
  type StudyPlan,
  type StudyProgress,
  type StudentAccount,
  type TutorMaterial,
  type TutorQuiz,
} from "../../api/modules/learningTutor";
import styles from "./index.module.less";

type Tab = "ask" | "explain" | "materials" | "practice" | "plan" | "progress";

const tabs: {
  id: Tab;
  label: string;
  icon: LucideIcon;
}[] = [
  { id: "ask", label: "Hỏi đáp", icon: MessageCircleQuestion },
  { id: "explain", label: "Giải bài", icon: Lightbulb },
  { id: "materials", label: "Tài liệu", icon: BookOpen },
  { id: "practice", label: "Luyện tập", icon: ClipboardList },
  { id: "plan", label: "Kế hoạch", icon: CalendarCheck },
  { id: "progress", label: "Tiến độ", icon: ChartNoAxesCombined },
];

const localDate = () => {
  const today = new Date();
  return [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");
};

function LearningTutorPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = useMemo<Tab>(() => {
    const pathTab = location.pathname.split("/").pop();
    return tabs.some((item) => item.id === pathTab)
      ? (pathTab as Tab)
      : "ask";
  }, [location.pathname]);
  const [student, setStudent] = useState<StudentAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [retryKey, setRetryKey] = useState(0);
  const [materials, setMaterials] = useState<TutorMaterial[]>([]);
  const [history, setHistory] = useState<LearningHistoryItem[]>([]);
  const [plans, setPlans] = useState<StudyPlan[]>([]);
  const [progress, setProgress] = useState<StudyProgress[]>([]);
  const [recommendations, setRecommendations] = useState<
    { subject: string; topic: string; accuracy: number; reason: string }[]
  >([]);
  const [answer, setAnswer] = useState<{
    text: string;
    sources: { title: string; excerpt: string }[];
  } | null>(null);
  const [quiz, setQuiz] = useState<TutorQuiz | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<number[]>([]);
  const [quizResult, setQuizResult] = useState<{
    score: number;
    total: number;
    feedback: {
      question_index: number;
      correct: boolean;
      correct_index: number;
      explanation: string;
    }[];
  } | null>(null);

  const refreshDashboard = useCallback(async () => {
    const [nextMaterials, nextHistory, nextPlans, nextProgress] =
      await Promise.all([
        learningTutorApi.materials(),
        learningTutorApi.history(),
        learningTutorApi.plans(),
        learningTutorApi.progress(),
      ]);
    setMaterials(nextMaterials);
    setHistory(nextHistory);
    setPlans(nextPlans);
    setProgress(nextProgress.topics);
    setRecommendations(nextProgress.recommendations);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([learningTutorApi.me(), refreshDashboard()])
      .then(([current]) => {
        if (!cancelled) {
          setStudent(current);
          setError("");
        }
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setStudent(null);
        setError(reason instanceof Error ? reason.message : "Không tải được dữ liệu.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshDashboard, retryKey]);

  const runAction = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Đã xảy ra lỗi.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.center}>
          <RefreshCw size={26} className={styles.spinIcon} />
          <span>Đang tải...</span>
        </div>
      </main>
    );
  }

  if (!student) {
    return (
      <main className={styles.page}>
        <section className={styles.card} role="alert">
          <h1>Không tải được không gian học tập</h1>
          <p className={styles.error}>{error || "Hãy đăng nhập lại vào QwenPaw."}</p>
          <button
            className={styles.primaryButton}
            onClick={() => setRetryKey((current) => current + 1)}
            type="button"
          >
            <RefreshCw size={14} />
            <span>Thử lại</span>
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            <Sparkles size={13} />
            <span>KHÔNG GIAN HỌC TẬP CÁ NHÂN</span>
          </p>
          <p className={styles.muted}>Hỏi bài, luyện tập và theo dõi tiến độ THPT của bạn.</p>
        </div>
        <div className={styles.account}>
          <UserRound size={15} />
          <span>Xin chào, <strong>{student.username}</strong></span>
        </div>
      </header>

      <nav className={styles.navigation} aria-label="Chức năng học tập">
        {tabs.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={tab === item.id ? styles.activeTab : ""}
              onClick={() => {
                navigate(`/learning/${item.id}`);
                setError("");
                setNotice("");
              }}
              type="button"
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {error && (
        <div className={styles.errorBanner} role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className={styles.noticeBanner} role="status">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      {(tab === "ask" || tab === "explain") && (
        <TutorPanel
          busy={busy}
          answer={answer}
          mode={tab === "explain" ? "explanation" : "question"}
          onModeChange={(mode) => navigate(`/learning/${mode === "question" ? "ask" : "explain"}`)}
          onAsk={(input) => runAction(async () => {
            const result = await learningTutorApi.ask(input);
            setAnswer({ text: result.answer, sources: result.sources });
            await refreshDashboard();
          })}
        />
      )}
      {tab === "materials" && (
        <MaterialsPanel
          materials={materials}
          busy={busy}
          onAdd={(input) => runAction(async () => {
            await learningTutorApi.addMaterial(input);
            await refreshDashboard();
            setNotice("Đã lưu tài liệu. Gia sư sẽ tìm nội dung liên quan khi bạn hỏi.");
          })}
          onDelete={(id) => runAction(async () => {
            await learningTutorApi.deleteMaterial(id);
            await refreshDashboard();
          })}
        />
      )}
      {tab === "practice" && (
        <PracticePanel
          busy={busy}
          quiz={quiz}
          answers={quizAnswers}
          result={quizResult}
          onGenerate={(input) => runAction(async () => {
            const result = await learningTutorApi.createQuiz(input);
            setQuiz(result);
            setQuizAnswers(result.questions.map(() => -1));
            setQuizResult(null);
          })}
          onAnswer={(question, answerIndex) => {
            setQuizAnswers((current) => current.map((value, index) => index === question ? answerIndex : value));
            setQuizResult(null);
          }}
          onSubmit={() => runAction(async () => {
            if (!quiz) return;
            const result = await learningTutorApi.submitQuiz(quiz.id, quizAnswers);
            setQuizResult(result);
            await refreshDashboard();
            setNotice("Đã lưu kết quả vào tiến độ học tập của bạn.");
          })}
        />
      )}
      {tab === "plan" && (
        <PlanPanel
          busy={busy}
          plans={plans}
          onCreate={(input) => runAction(async () => {
            await learningTutorApi.createPlan(input);
            await refreshDashboard();
            setNotice("Đã tạo kế hoạch học cá nhân.");
          })}
          onToggleTask={(planId, taskIndex, completed) => runAction(async () => {
            await learningTutorApi.completeTask(planId, taskIndex, completed);
            await refreshDashboard();
          })}
        />
      )}
      {tab === "progress" && (
        <ProgressPanel
          progress={progress}
          recommendations={recommendations}
          history={history}
        />
      )}
    </main>
  );
}

function AcademicFields() {
  return (
    <>
      <label>
        Môn học
        <input name="subject" required maxLength={80} placeholder="Ví dụ: Toán" />
      </label>
      <label>
        Khối lớp
        <select name="grade" defaultValue="10">
          <option value="10">Lớp 10</option>
          <option value="11">Lớp 11</option>
          <option value="12">Lớp 12</option>
        </select>
      </label>
    </>
  );
}

function TutorPanel({
  busy,
  answer,
  mode,
  onModeChange,
  onAsk,
}: {
  busy: boolean;
  answer: { text: string; sources: { title: string; excerpt: string }[] } | null;
  mode: "question" | "explanation";
  onModeChange: (mode: "question" | "explanation") => void;
  onAsk: (input: {
    question: string;
    subject: string;
    grade: number;
    topic: string;
    mode: "question" | "explanation";
  }) => Promise<void>;
}) {
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void onAsk({
      question: String(form.get("question") || ""),
      subject: String(form.get("subject") || ""),
      grade: Number(form.get("grade") || 10),
      topic: String(form.get("topic") || "Chưa phân loại"),
      mode,
    });
  };
  return (
    <div className={styles.columns}>
      <section className={styles.card}>
        <SectionHeading title="Hỏi gia sư" description="Câu trả lời ưu tiên tài liệu bạn đã thêm trong tab Tài liệu." />
        <form className={styles.form} onSubmit={submit}>
          <div className={styles.formGrid}><AcademicFields /></div>
          <label>Chủ đề<input name="topic" maxLength={120} placeholder="Ví dụ: Hàm số bậc hai" /></label>
          <div className={styles.modeButtons}>
            <button type="button" className={mode === "question" ? styles.selected : ""} onClick={() => onModeChange("question")}>Hỏi kiến thức</button>
            <button type="button" className={mode === "explanation" ? styles.selected : ""} onClick={() => onModeChange("explanation")}>Giải thích bài tập</button>
          </div>
          <label>
            {mode === "question" ? "Câu hỏi" : "Đề bài cần giải thích"}
            <textarea name="question" required maxLength={4000} rows={6} placeholder="Nhập câu hỏi hoặc đề bài…" />
          </label>
          <button className={styles.primaryButton} disabled={busy} type="submit">
            {busy ? (
              <>
                <RefreshCw size={14} className={styles.spinIcon} />
                <span>Gia sư đang suy nghĩ…</span>
              </>
            ) : (
              <>
                <Send size={14} />
                <span>Gửi câu hỏi</span>
              </>
            )}
          </button>
        </form>
      </section>
      <section className={styles.card}>
        <SectionHeading title="Lời giải" description="Lịch sử hỏi đáp được lưu riêng cho tài khoản của bạn." />
        {answer ? (
          <>
            <div className={styles.answer}>{answer.text}</div>
            {answer.sources.length > 0 && (
              <div className={styles.sources}>
                <strong>
                  <BookMarked size={14} />
                  <span>Nguồn tài liệu được tham khảo</span>
                </strong>
                {answer.sources.map((source, index) => (
                  <p key={`${source.title}-${index}`}>
                    <strong>{source.title}:</strong> {source.excerpt}
                  </p>
                ))}
              </div>
            )}
          </>
        ) : <EmptyState text="Câu trả lời của gia sư sẽ xuất hiện ở đây." />}
      </section>
    </div>
  );
}

function MaterialsPanel({
  materials,
  busy,
  onAdd,
  onDelete,
}: {
  materials: TutorMaterial[];
  busy: boolean;
  onAdd: (input: { subject: string; grade: number; title: string; content: string }) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void onAdd({
      subject: String(form.get("subject") || ""),
      grade: Number(form.get("grade") || 10),
      title: String(form.get("title") || ""),
      content: String(form.get("content") || ""),
    });
  };
  return (
    <div className={styles.columns}>
      <section className={styles.card}>
        <SectionHeading title="Thêm tài liệu học" description="Dán ghi chú hoặc nội dung bài học để gia sư tìm kiếm làm ngữ cảnh trả lời (RAG)." />
        <form className={styles.form} onSubmit={submit}>
          <div className={styles.formGrid}><AcademicFields /></div>
          <label>Tiêu đề tài liệu<input name="title" required maxLength={150} placeholder="Tên chương, bài học…" /></label>
          <label>Nội dung<textarea name="content" required maxLength={50000} rows={10} placeholder="Dán nội dung tài liệu vào đây…" /></label>
          <button className={styles.primaryButton} disabled={busy} type="submit">
            {busy ? (
              <>
                <RefreshCw size={14} className={styles.spinIcon} />
                <span>Đang lưu…</span>
              </>
            ) : (
              <>
                <Plus size={14} />
                <span>Lưu tài liệu</span>
              </>
            )}
          </button>
        </form>
      </section>
      <section className={styles.card}>
        <SectionHeading title="Tài liệu của tôi" description={`${materials.length} tài liệu đã lưu`} />
        {materials.length ? materials.map((material) => (
          <article className={styles.listItem} key={material.id}>
            <div><strong>{material.title}</strong><p>{material.subject} · Lớp {material.grade}</p></div>
            <button
              className={styles.textButton}
              disabled={busy}
              onClick={() => void onDelete(material.id)}
              type="button"
            >
              <Trash2 size={13} />
              <span>Xóa</span>
            </button>
          </article>
        )) : <EmptyState text="Chưa có tài liệu. Thêm học liệu để câu trả lời có căn cứ." />}
      </section>
    </div>
  );
}

function PracticePanel({
  busy,
  quiz,
  answers,
  result,
  onGenerate,
  onAnswer,
  onSubmit,
}: {
  busy: boolean;
  quiz: TutorQuiz | null;
  answers: number[];
  result: { score: number; total: number; feedback: { question_index: number; correct: boolean; correct_index: number; explanation: string }[] } | null;
  onGenerate: (input: { subject: string; topic: string; grade: number; difficulty: "easy" | "medium" | "hard"; count: number }) => Promise<void>;
  onAnswer: (question: number, answer: number) => void;
  onSubmit: () => Promise<void>;
}) {
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void onGenerate({
      subject: String(form.get("subject") || ""),
      topic: String(form.get("topic") || ""),
      grade: Number(form.get("grade") || 10),
      difficulty: String(form.get("difficulty") || "medium") as "easy" | "medium" | "hard",
      count: Number(form.get("count") || 5),
    });
  };
  return (
    <div className={styles.columns}>
      <section className={styles.card}>
        <SectionHeading title="Tạo bài luyện tập" description="Gia sư tạo câu hỏi trắc nghiệm và dùng tài liệu môn học nếu có." />
        <form className={styles.form} onSubmit={submit}>
          <div className={styles.formGrid}><AcademicFields /></div>
          <label>Chủ đề<input name="topic" required maxLength={120} placeholder="Ví dụ: Đạo hàm" /></label>
          <div className={styles.formGrid}>
            <label>Độ khó<select name="difficulty" defaultValue="medium"><option value="easy">Cơ bản</option><option value="medium">Trung bình</option><option value="hard">Nâng cao</option></select></label>
            <label>Số câu<select name="count" defaultValue="5"><option value="3">3 câu</option><option value="5">5 câu</option><option value="10">10 câu</option></select></label>
          </div>
          <button className={styles.primaryButton} disabled={busy} type="submit">
            {busy ? (
              <>
                <RefreshCw size={14} className={styles.spinIcon} />
                <span>Đang tạo đề…</span>
              </>
            ) : (
              <>
                <Plus size={14} />
                <span>Tạo bài luyện tập</span>
              </>
            )}
          </button>
        </form>
      </section>
      <section className={styles.card}>
        <SectionHeading title="Bài làm" description={quiz ? `${quiz.subject} · ${quiz.topic}` : "Tạo một bài luyện tập để bắt đầu."} />
        {quiz ? (
          <div className={styles.quizList}>
            {quiz.questions.map((question, questionIndex) => (
              <fieldset className={styles.questionCard} key={`${quiz.id}-${questionIndex}`}>
                <legend>{questionIndex + 1}. {question.prompt}</legend>
                {question.options.map((option, optionIndex) => (
                  <label className={styles.option} key={optionIndex}>
                    <input type="radio" name={`question-${questionIndex}`} checked={answers[questionIndex] === optionIndex} disabled={Boolean(result)} onChange={() => onAnswer(questionIndex, optionIndex)} />
                    {option}
                  </label>
                ))}
                {result && (
                  <p className={result.feedback[questionIndex]?.correct ? styles.correct : styles.incorrect}>
                    {result.feedback[questionIndex]?.correct ? "Chính xác." : `Chưa đúng. Đáp án: ${question.options[result.feedback[questionIndex]?.correct_index]}.`} {result.feedback[questionIndex]?.explanation}
                  </p>
                )}
              </fieldset>
            ))}
            {!result && (
              <button
                className={styles.primaryButton}
                disabled={busy || answers.some((value) => value < 0)}
                onClick={() => void onSubmit()}
                type="button"
              >
                {busy ? (
                  <>
                    <RefreshCw size={14} className={styles.spinIcon} />
                    <span>Đang nộp…</span>
                  </>
                ) : (
                  <>
                    <Send size={14} />
                    <span>Nộp bài</span>
                  </>
                )}
              </button>
            )}
            {result && (
              <div className={styles.score}>
                <Award size={18} />
                <span>Kết quả: {result.score}/{result.total} câu đúng</span>
              </div>
            )}
          </div>
        ) : <EmptyState text="Bài luyện tập sẽ hiển thị tại đây." />}
      </section>
    </div>
  );
}

function PlanPanel({
  busy,
  plans,
  onCreate,
  onToggleTask,
}: {
  busy: boolean;
  plans: StudyPlan[];
  onCreate: (input: { subject: string; grade: number; goal: string; start_date: string; days: number; daily_minutes: number; weekdays: number[] }) => Promise<void>;
  onToggleTask: (planId: string, taskIndex: number, completed: boolean) => Promise<void>;
}) {
  const [weekdays, setWeekdays] = useState([0, 1, 2, 3, 4]);
  const weekdayNames = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void onCreate({
      subject: String(form.get("subject") || ""),
      grade: Number(form.get("grade") || 10),
      goal: String(form.get("goal") || ""),
      start_date: String(form.get("start_date") || localDate()),
      days: Number(form.get("days") || 7),
      daily_minutes: Number(form.get("daily_minutes") || 30),
      weekdays,
    });
  };
  return (
    <div className={styles.columns}>
      <section className={styles.card}>
        <SectionHeading title="Lập kế hoạch học cá nhân" description="Gia sư chia mục tiêu thành các buổi học dựa trên lịch và thời lượng bạn chọn." />
        <form className={styles.form} onSubmit={submit}>
          <div className={styles.formGrid}><AcademicFields /></div>
          <label>Mục tiêu học tập<input name="goal" required maxLength={500} placeholder="Ví dụ: Nắm vững chương hàm số bậc hai" /></label>
          <div className={styles.formGrid}>
            <label>Bắt đầu từ<input name="start_date" type="date" defaultValue={localDate()} required /></label>
            <label>Khoảng ngày<input name="days" type="number" min={1} max={30} defaultValue={7} required /></label>
          </div>
          <label>Thời lượng mỗi buổi (phút)<input name="daily_minutes" type="number" min={10} max={180} defaultValue={30} required /></label>
          <div className={styles.weekdays}>
            <span>Ngày có thể học</span>
            <div className={styles.weekdayList}>
              {weekdayNames.map((name, day) => (
                <label key={day}>
                  <input
                    type="checkbox"
                    checked={weekdays.includes(day)}
                    onChange={() =>
                      setWeekdays((current) =>
                        current.includes(day)
                          ? current.filter((value) => value !== day)
                          : [...current, day].sort(),
                      )
                    }
                  />
                  <span>{name}</span>
                </label>
              ))}
            </div>
          </div>
          <button className={styles.primaryButton} disabled={busy || weekdays.length === 0} type="submit">
            {busy ? (
              <>
                <RefreshCw size={14} className={styles.spinIcon} />
                <span>Đang lập kế hoạch…</span>
              </>
            ) : (
              <>
                <Plus size={14} />
                <span>Tạo kế hoạch</span>
              </>
            )}
          </button>
        </form>
      </section>
      <section className={styles.card}>
        <SectionHeading title="Kế hoạch của tôi" description="Đánh dấu hoàn thành để cập nhật tiến độ." />
        {plans.length ? plans.map((plan) => (
          <article className={styles.plan} key={plan.id}>
            <div className={styles.planTitle}><div><strong>{plan.subject} · Lớp {plan.grade}</strong><p>{plan.goal}</p></div><span>{plan.tasks.filter((task) => task.completed).length}/{plan.tasks.length} buổi</span></div>
            {plan.tasks.map((task, index) => (
              <label className={styles.task} key={`${plan.id}-${task.date}-${index}`}>
                <input type="checkbox" checked={task.completed} disabled={busy} onChange={(event) => void onToggleTask(plan.id, index, event.target.checked)} />
                <div><strong>{task.date} · {task.title}</strong><p>{task.focus} — {task.activity}</p><small>{task.minutes} phút</small></div>
              </label>
            ))}
          </article>
        )) : <EmptyState text="Chưa có kế hoạch học. Hãy nhập mục tiêu để tạo kế hoạch đầu tiên." />}
      </section>
    </div>
  );
}

function ProgressPanel({
  progress,
  recommendations,
  history,
}: {
  progress: StudyProgress[];
  recommendations: { subject: string; topic: string; accuracy: number; reason: string }[];
  history: LearningHistoryItem[];
}) {
  const totalAnswered = useMemo(() => progress.reduce((sum, item) => sum + item.total, 0), [progress]);
  return (
    <div className={styles.progressGrid}>
      <section className={styles.card}>
        <SectionHeading title="Tiến độ theo chủ đề" description={`${progress.length} chủ đề đã luyện · ${totalAnswered} câu đã làm`} />
        {progress.length ? progress.map((item) => (
          <article className={styles.progressItem} key={`${item.subject}-${item.topic}`}>
            <div><strong>{item.subject} · {item.topic}</strong><span>{Math.round(item.accuracy * 100)}%</span></div>
            <div className={styles.progressTrack}><span style={{ width: `${Math.round(item.accuracy * 100)}%` }} /></div>
            <small>{item.correct}/{item.total} câu đúng · {item.attempts} lượt làm</small>
          </article>
        )) : <EmptyState text="Hãy hoàn thành bài luyện tập để xem tiến độ theo chủ đề." />}
      </section>
      <section className={styles.card}>
        <SectionHeading title="Gợi ý ôn tập" description="Ưu tiên những chủ đề có kết quả luyện tập thấp." />
        {recommendations.length ? recommendations.map((item) => (
          <article className={styles.recommendation} key={`${item.subject}-${item.topic}`}>
            <strong>{item.subject} · {item.topic}</strong>
            <p>{item.reason}</p>
            <span>Độ chính xác hiện tại: {Math.round(item.accuracy * 100)}%</span>
          </article>
        )) : <EmptyState text="Chưa có chủ đề cần ưu tiên. Hãy làm bài luyện tập để nhận gợi ý." />}
      </section>
      <section className={`${styles.card} ${styles.historyCard}`}>
        <SectionHeading title="Lịch sử hỏi đáp" description="Các câu hỏi gần đây đã lưu trong tài khoản này." />
        {history.length ? history.slice(0, 10).map((item) => (
          <article className={styles.historyItem} key={item.id}>
            <div><strong>{item.subject} · {item.topic}</strong><time>{new Date(item.created_at * 1000).toLocaleString()}</time></div>
            <p>{item.prompt}</p>
            <details><summary>Xem câu trả lời</summary><p>{item.response}</p></details>
          </article>
        )) : <EmptyState text="Lịch sử câu hỏi sẽ hiển thị tại đây." />}
      </section>
    </div>
  );
}

function SectionHeading({ title, description }: { title: string; description: string }) {
  return <div className={styles.sectionHeading}><h2>{title}</h2><p>{description}</p></div>;
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className={styles.empty}>
      <GraduationCap size={28} className={styles.emptyIcon} />
      <span>{text}</span>
    </div>
  );
}

export default LearningTutorPage;
