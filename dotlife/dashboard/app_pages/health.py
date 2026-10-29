import polars as pl
import streamlit as st

from dotlife.config import all_categories
from dotlife.dashboard.data import dataset, report
from dotlife.validate import FileReport, Severity, group_problems, plural

SEVERITY_COLORS = {Severity.ERROR: "red", Severity.WARNING: "orange"}


def findings(file: FileReport) -> str:
    """Summarise a file's findings for the table.

    Args:
        file: One category's report.

    Returns:
        E.g. "1 warning · 1 gap · 4 days left out", or "OK".
    """
    errors = sum(problem.severity is Severity.ERROR for problem in file.problems)
    warnings = len(file.problems) - errors
    parts = [
        plural(errors, "error") if errors else "",
        plural(warnings, "warning") if warnings else "",
        plural(len(file.gaps), "gap") if file.gaps else "",
        f"{plural(file.days_skipped, 'day')} left out" if file.days_skipped else "",
    ]
    return " · ".join(part for part in parts if part) or "OK"


data = dataset()
checked = report()
labels = {
    category.name: category.label for category in all_categories(data.source.config)
}

st.title("Data health")
st.caption(
    "The same checks as `dotlife validate`, against FORMAT.md. Gaps and odd values "
    "are reported here; nothing is filled in or changed. Fix problems at the source "
    "or in its import, never by editing values to pass."
)

with st.container(horizontal=True):
    st.metric("Errors", checked.error_count, border=True)
    st.metric("Warnings", checked.warning_count, border=True)
    st.metric("Categories with data", len(checked.files), border=True)
    st.metric(
        "Data up to",
        f"{checked.as_of:%d %b %Y}" if checked.as_of else "None",
        border=True,
    )

with st.container(border=True):
    st.subheader("Worth a look")
    lines = [
        (severity, "config.toml", text)
        for severity, text in group_problems(checked.problems)
    ]
    for file in checked.files:
        name = labels.get(file.category, file.category)
        lines += [
            (severity, name, text) for severity, text in group_problems(file.problems)
        ]
        lines += [
            (None, name, f"no data {start}" + ("" if start == end else f" to {end}"))
            for start, end in file.gaps
        ]
    if not lines:
        st.markdown("Nothing to report.")
    for severity, name, text in lines:
        badge = (
            f":{SEVERITY_COLORS[severity]}-badge[{severity.value.title()}]"
            if severity
            else ":blue-badge[Gap]"
        )
        st.markdown(f"{badge} **{name}:** {text}")

with st.container(border=True):
    st.subheader("Every category")
    only_findings = st.toggle(
        "Only categories with findings", key="health_only_findings"
    )
    rows = [
        {
            "Category": labels.get(file.category, file.category),
            "Rows": file.rows,
            "From": file.first_date,
            "To": file.last_date,
            "Findings": findings(file),
        }
        for file in checked.files
        if not only_findings or findings(file) != "OK"
    ]
    st.dataframe(
        pl.DataFrame(rows),
        hide_index=True,
        alt="Rows, dates and findings for each category",
    )
    if checked.missing:
        missing = ", ".join(labels.get(name, name) for name in checked.missing)
        st.caption(f"No data, so not shown: {missing}.")
    if checked.disabled:
        disabled = ", ".join(labels.get(name, name) for name in checked.disabled)
        st.caption(f"Switched off in config.toml: {disabled}.")
