"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiFetch, errorMessage } from "@/lib/api";
import { faNum } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import Spinner from "@/components/Spinner";

const phoneSchema = z.object({
  phone_number: z
    .string()
    .regex(/^09\d{9}$/, "شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود"),
  full_name: z.string().optional(),
});

type PhoneForm = z.infer<typeof phoneSchema>;

const codeSchema = z.object({
  code: z.string().regex(/^\d{6}$/, "کد باید ۶ رقم باشد"),
});

const RESEND_SECONDS = 120;

export default function OtpAuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resendIn, setResendIn] = useState(0);
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const otpInputs = useRef<Array<HTMLInputElement | null>>([]);

  const phoneForm = useForm<PhoneForm>({
    resolver: zodResolver(phoneSchema),
    defaultValues: { phone_number: "", full_name: "" },
  });

  const codeForm = useForm<{ code: string }>({
    resolver: zodResolver(codeSchema),
    defaultValues: { code: "" },
  });

  // Resend countdown timer.
  useEffect(() => {
    if (resendIn <= 0) return;
    const t = setInterval(() => setResendIn((v) => v - 1), 1000);
    return () => clearInterval(t);
  }, [resendIn]);

  // Keep the react-hook-form value in sync with the boxed input.
  useEffect(() => {
    codeForm.setValue("code", otp.join(""), { shouldValidate: true });
  }, [otp, codeForm]);

  const requestOtp = async (values: PhoneForm) => {
    setError(null);
    try {
      await apiFetch(
        "/auth/otp/request/",
        {
          method: "POST",
          body: JSON.stringify({ phone_number: values.phone_number }),
        },
        false
      );
      setPhone(values.phone_number);
      setFullName(values.full_name ?? "");
      setStep("code");
      setResendIn(RESEND_SECONDS);
      setTimeout(() => otpInputs.current[0]?.focus(), 50);
    } catch (e) {
      setError(errorMessage((e as { data?: unknown }).data, "خطا در ارسال کد"));
    }
  };

  const verifyOtp = async () => {
    setError(null);
    try {
      const data = await apiFetch<import("@/types").AuthResponse>(
        "/auth/otp/verify/",
        {
          method: "POST",
          body: JSON.stringify({
            phone_number: phone,
            code: otp.join(""),
            full_name: mode === "register" ? fullName : undefined,
          }),
        },
        false
      );
      setAuth(data.tokens, data.user);
      router.push("/dashboard");
    } catch (e) {
      setError(errorMessage((e as { data?: unknown }).data, "کد وارد شده صحیح نیست"));
      setOtp(["", "", "", "", "", ""]);
      setTimeout(() => otpInputs.current[0]?.focus(), 50);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    const digit = value.replace(/\D/g, "").slice(-1);
    const next = [...otp];
    next[index] = digit;
    setOtp(next);
    // Auto-advance to the next box.
    if (digit && index < 5) otpInputs.current[index + 1]?.focus();
  };

  const handleOtpKeyDown = (
    index: number,
    e: React.KeyboardEvent<HTMLInputElement>
  ) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      otpInputs.current[index - 1]?.focus();
    }
  };

  const submitting = phoneForm.formState.isSubmitting || codeForm.formState.isSubmitting;

  return (
    <div className="w-full max-w-md rounded-2xl border border-navy/10 bg-white p-6 shadow-xl sm:p-8">
      {step === "phone" ? (
        <form onSubmit={phoneForm.handleSubmit(requestOtp)} noValidate>
          <h2 className="text-xl font-bold">
            {mode === "login" ? "ورود به حساب کاربری" : "ثبت‌نام در کلینیک"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-navy/60">
            {mode === "login"
              ? "شماره موبایل خود را وارد کنید؛ کد تایید برای شما پیامک می‌شود."
              : "با وارد کردن شماره موبایل، حساب کاربری شما ساخته می‌شود."}
          </p>

          {mode === "register" && (
            <div className="mt-5">
              <label htmlFor="full_name" className="mb-1.5 block text-sm font-medium">
                نام و نام خانوادگی
              </label>
              <input
                id="full_name"
                type="text"
                autoComplete="name"
                placeholder="مثلاً علی رضایی"
                className="w-full rounded-xl border border-navy/20 px-4 py-3 text-base outline-none transition-colors focus:border-emerald"
                {...phoneForm.register("full_name")}
              />
            </div>
          )}

          <div className="mt-5">
            <label htmlFor="phone_number" className="mb-1.5 block text-sm font-medium">
              شماره موبایل
            </label>
            <input
              id="phone_number"
              type="tel"
              inputMode="numeric"
              dir="ltr"
              autoComplete="tel"
              placeholder="09123456789"
              className="w-full rounded-xl border border-navy/20 px-4 py-3 text-base outline-none transition-colors focus:border-emerald"
              {...phoneForm.register("phone_number")}
            />
            {phoneForm.formState.errors.phone_number && (
              <p className="mt-1.5 text-sm text-red-600">
                {phoneForm.formState.errors.phone_number.message}
              </p>
            )}
          </div>

          {error && (
            <p role="alert" className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-emerald px-5 text-base font-bold text-white shadow-md transition-colors hover:bg-emerald-light disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting && <Spinner />}
            دریافت کد تایید
          </button>

          <p className="mt-4 text-center text-sm text-navy/60">
            {mode === "login" ? (
              <>
                حساب کاربری ندارید؟{" "}
                <Link href="/register" title="ثبت‌نام" className="font-semibold text-emerald hover:underline">
                  ثبت‌نام کنید
                </Link>
              </>
            ) : (
              <>
                قبلاً ثبت‌نام کرده‌اید؟{" "}
                <Link href="/login" title="ورود" className="font-semibold text-emerald hover:underline">
                  وارد شوید
                </Link>
              </>
            )}
          </p>
        </form>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            verifyOtp();
          }}
        >
          <button
            type="button"
            onClick={() => setStep("phone")}
            className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-navy/60 hover:text-navy"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 rotate-180" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M9 6l6 6-6 6" />
            </svg>
            تغییر شماره
          </button>

          <h2 className="text-xl font-bold">کد تایید را وارد کنید</h2>
          <p className="mt-2 text-sm leading-6 text-navy/60">
            کد ۶ رقمی ارسال‌شده به شماره{" "}
            <span dir="ltr" className="font-bold text-navy">
              {faNum(phone)}
            </span>{" "}
            را وارد کنید.
          </p>

          <div className="mt-6 flex justify-between gap-2" dir="ltr">
            {otp.map((digit, i) => (
              <input
                key={i}
                ref={(el) => {
                  otpInputs.current[i] = el;
                }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleOtpChange(i, e.target.value)}
                onKeyDown={(e) => handleOtpKeyDown(i, e)}
                aria-label={`رقم ${i + 1} کد تایید`}
                className="h-14 w-full rounded-xl border border-navy/20 text-center text-xl font-bold outline-none transition-colors focus:border-emerald focus:ring-2 focus:ring-emerald/30"
              />
            ))}
          </div>

          {error && (
            <p role="alert" className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting || otp.join("").length !== 6}
            className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-emerald px-5 text-base font-bold text-white shadow-md transition-colors hover:bg-emerald-light disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting && <Spinner />}
            تایید و ورود
          </button>

          <p className="mt-4 text-center text-sm text-navy/60">
            {resendIn > 0 ? (
              <>ارسال مجدد کد تا {faNum(resendIn)} ثانیه دیگر</>
            ) : (
              <button
                type="button"
                onClick={() => requestOtp({ phone_number: phone, full_name: fullName })}
                className="font-semibold text-emerald hover:underline"
              >
                ارسال مجدد کد
              </button>
            )}
          </p>
        </form>
      )}
    </div>
  );
}