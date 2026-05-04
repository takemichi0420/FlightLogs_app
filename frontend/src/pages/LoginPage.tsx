import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "../lib/api";
import { AuthUser } from "../lib/types";

const schema = z.object({
  username: z.string().min(1, "ユーザー名を入力してください"),
  password: z.string().min(1, "パスワードを入力してください"),
});

const registerSchema = z.object({
  username: z.string().min(1, "ユーザー名を入力してください"),
  email: z.string().email("有効なメールアドレスを入力してください"),
  password: z.string().min(8, "8文字以上で入力してください"),
});

type Props = {
  onSuccess: (user: AuthUser) => void;
};

export function LoginPage({ onSuccess }: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
  });
  const registerForm = useForm<z.infer<typeof registerSchema>>({
    resolver: zodResolver(registerSchema),
  });

  async function onSubmit(values: z.infer<typeof schema>) {
    const response = await api.post<AuthUser>("/auth/login/", values);
    onSuccess(response.data);
  }

  async function onRegister(values: z.infer<typeof registerSchema>) {
    const response = await api.post<AuthUser>("/auth/register/", values);
    onSuccess(response.data);
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="panel grid max-w-5xl overflow-hidden md:grid-cols-[1.15fr_0.85fr]">
        <section className="bg-[linear-gradient(160deg,#0d2130_0%,#0f5677_48%,#17a7d7_100%)] p-8 text-white md:p-12">
          <p className="text-xs font-semibold text-sky-100">運用準備</p>
          <h1 className="mt-5 max-w-md text-4xl font-semibold leading-tight">
            法定飛行記録を、ログから組み上げる。
          </h1>
          <p className="mt-6 max-w-md text-sm leading-7 text-sky-50/90">
            ArduPilot のフライトログ、正式な気象入力、確定処理、PDF 出力をひとつの業務画面にまとめた MVP です。
          </p>
        </section>
        <section className="p-8 md:p-12">
          <p className="text-xs font-semibold text-sky-700">ログイン</p>
          <h2 className="mt-3 text-2xl font-semibold text-ink">サインイン</h2>
          <form className="mt-8 space-y-5" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label className="label">ユーザー名</label>
              <input className="input" {...register("username")} />
              {errors.username ? <p className="mt-2 text-sm text-rose-600">{errors.username.message}</p> : null}
            </div>
            <div>
              <label className="label">パスワード</label>
              <input className="input" type="password" {...register("password")} />
              {errors.password ? <p className="mt-2 text-sm text-rose-600">{errors.password.message}</p> : null}
            </div>
            <button className="btn-primary w-full" disabled={isSubmitting} type="submit">
              {isSubmitting ? "ログイン中..." : "ログイン"}
            </button>
          </form>
          <div className="mt-8 border-t border-slate-200 pt-8">
            <p className="text-xs font-semibold text-slate-500">新規登録</p>
            <form className="mt-4 space-y-4" onSubmit={registerForm.handleSubmit(onRegister)}>
              <div>
                <label className="label">ユーザー名</label>
                <input className="input" {...registerForm.register("username")} />
                {registerForm.formState.errors.username ? <p className="mt-2 text-sm text-rose-600">{registerForm.formState.errors.username.message}</p> : null}
              </div>
              <div>
                <label className="label">メールアドレス</label>
                <input className="input" {...registerForm.register("email")} />
                {registerForm.formState.errors.email ? <p className="mt-2 text-sm text-rose-600">{registerForm.formState.errors.email.message}</p> : null}
              </div>
              <div>
                <label className="label">パスワード</label>
                <input className="input" type="password" {...registerForm.register("password")} />
                {registerForm.formState.errors.password ? <p className="mt-2 text-sm text-rose-600">{registerForm.formState.errors.password.message}</p> : null}
              </div>
              <button className="btn-secondary w-full" disabled={registerForm.formState.isSubmitting} type="submit">
                {registerForm.formState.isSubmitting ? "作成中..." : "アカウント作成"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}
