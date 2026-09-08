"""Slot generation and concurrency-safe booking for appointments."""
import datetime
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, DoctorSchedule, Holiday

MIN_BOOKING_LEAD_HOURS = 2


def _today_local() -> datetime.date:
    return timezone.localdate()


def _minutes(t: datetime.time) -> int:
    return t.hour * 60 + t.minute


def _time_from_minutes(m: int) -> datetime.time:
    return (datetime.datetime(2000, 1, 1) + datetime.timedelta(minutes=m)).time()


def iter_slot_times(schedule: DoctorSchedule) -> list[tuple[datetime.time, datetime.time]]:
    """Generate (start, end) slot pairs for a schedule, respecting the break."""
    start = _minutes(schedule.start_work)
    end = _minutes(schedule.end_work)
    duration = schedule.session_duration
    break_start = _minutes(schedule.break_start) if schedule.break_start else None
    break_end = _minutes(schedule.break_end) if schedule.break_end else None

    slots = []
    t = start
    while t + duration <= end:
        # Skip slots overlapping the break window.
        if break_start is not None and break_end is not None:
            if t < break_end and t + duration > break_start:
                t = break_end
                continue
        slots.append((_time_from_minutes(t), _time_from_minutes(t + duration)))
        t += duration
    return slots


def free_slots(doctor_id: uuid.UUID, date: datetime.date) -> list[dict]:
    """Return free time slots for a doctor on a given date."""
    date = date or _today_local()
    schedules = DoctorSchedule.objects.filter(doctor_id=doctor_id, day_of_week=_django_weekday(date))
    if not schedules.exists():
        return []

    is_holiday = Holiday.objects.filter(date=date).filter(models_or_doctor(doctor_id)).exists()
    if is_holiday:
        return []

    booked = set(
        Appointment.objects.filter(
            doctor_id=doctor_id,
            appointment_date=date,
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
        ).values_list("start_time", flat=True)
    )

    result = []
    for schedule in schedules:
        for start, end in iter_slot_times(schedule):
            if start not in booked:
                result.append(
                    {
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M"),
                    }
                )
    result.sort(key=lambda s: s["start"])
    return result


def available_days(doctor_id: uuid.UUID, days: int = 30) -> list[dict]:
    """List the next `days` days with their free-slot counts (for the Jalali calendar)."""
    today = _today_local()
    out = []
    for offset in range(days):
        date = today + datetime.timedelta(days=offset)
        slots = free_slots(doctor_id, date)
        if slots:
            out.append({"date": date.isoformat(), "free_slots": len(slots)})
    return out


def book_appointment(
    *,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    service_type: str,
    date: datetime.date,
    start_time: str,
    description: str = "",
) -> Appointment:
    """Book an appointment inside a transaction with a row-level lock.

    Concurrency strategy:
      1. Lock the doctor's schedule rows with select_for_update, serializing
         all bookings for the same doctor (PostgreSQL honours FOR UPDATE).
      2. Re-check availability inside the lock.
      3. Insert; a UNIQUE constraint on (doctor, date, start_time) for active
         statuses acts as a final backstop against races.
    Raises ValueError with a Persian message on any conflict.
    """
    if date < _today_local():
        raise ValueError("امکان رزرو نوبت در تاریخ گذشته وجود ندارد")

    # Minimum 2-hour lead time before the appointment (spec).
    now = timezone.localtime()
    slot_datetime = datetime.datetime.combine(date, datetime.time.fromisoformat(start_time))
    slot_datetime = timezone.make_aware(slot_datetime)
    if slot_datetime - now < datetime.timedelta(hours=MIN_BOOKING_LEAD_HOURS):
        raise ValueError(f"حداقل {MIN_BOOKING_LEAD_HOURS} ساعت قبل از نوبت باید رزرو کنید")

    try:
        with transaction.atomic():
            schedules = list(
                DoctorSchedule.objects.select_for_update().filter(
                    doctor_id=doctor_id, day_of_week=_django_weekday(date)
                )
            )
            if not schedules:
                raise ValueError("این پزشک در تاریخ مورد نظر نوبت خالی ندارد. لطفاً تاریخ یا پزشک دیگری انتخاب کنید")

            is_holiday = Holiday.objects.filter(date=date).filter(
                models_or_doctor(doctor_id)
            ).exists()
            if is_holiday:
                raise ValueError("این تاریخ تعطیل است")

            free = {s["start"] for s in free_slots(doctor_id, date)}
            if start_time not in free:
                raise ValueError("متاسفانه این زمان پر شد؛ لطفاً زمان دیگری انتخاب کنید")

            duration = schedules[0].session_duration
            end = (
                datetime.datetime.combine(date, datetime.time.fromisoformat(start_time))
                + datetime.timedelta(minutes=duration)
            ).time()

            appointment = Appointment.objects.create(
                patient_id=patient_id,
                doctor_id=doctor_id,
                service_type=service_type,
                appointment_date=date,
                start_time=start_time,
                end_time=end,
                description=description,
            )
        return appointment
    except IntegrityError:
        raise ValueError("متاسفانه این زمان پر شد؛ لطفاً زمان دیگری انتخاب کنید")


def _django_weekday(date: datetime.date) -> int:
    """Python's weekday(): Monday=0…Sunday=6 — no Persian-calendar mapping needed."""
    return date.weekday()


def models_or_doctor(doctor_id):
    from django.db.models import Q

    return Q(doctor_id=doctor_id) | Q(doctor__isnull=True)