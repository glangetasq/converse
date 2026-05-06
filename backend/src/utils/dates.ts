export function parseOptionalDate(value: string | undefined): Date | null {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date;
}

export function maxDate(dates: Array<Date | null>): Date | null {
  const validDates = dates.filter((date): date is Date => date !== null);
  if (validDates.length === 0) {
    return null;
  }

  return new Date(Math.max(...validDates.map((date) => date.getTime())));
}
