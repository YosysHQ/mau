"""Diagnostic reporting using source tracking strings.

.. warning::
  The API for error reporting hasn't been fully designed yet and is likely to change.

"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .. import source_str


@dataclass
class InputError(Exception):
    """An error in user input.

    .. note::
      The API for error reporting hasn't been fully designed yet and is likely to change. Something
      simple to raise one-off errors like this will certainly stay though.

    """

    where: str | None
    message: str

    def __str__(self) -> str:
        source_map = source_str.source_map(self.where or "")
        if not source_map:
            return self.message
        report = Report(source_map.detached(), self.message)
        return str(report)

    def fallback_span(self, where_else: str):
        if not source_str.source_map(self.where or ""):
            self.where = where_else


@dataclass(eq=False)
class Report:
    """Collects diagnostic information associated to specific source locations.

    .. warning::
      The API for error reporting hasn't been fully designed yet and is likely to change. This class
      in particular will undergo backwards incompatible API changes and should be considered
      internal to this library for now.

    """

    spans: source_str.SourceSpans

    message: str

    def __str__(self) -> str:
        out = [f"{self.message}\n"]

        for file, spans in self.spans.close_gaps().group_by_file().items():
            if file.content is None:
                raise NotImplementedError

            highlights: dict[int, list[str]] = defaultdict(list)

            for span in spans.spans:
                for pos in range(span.file_start, span.file_end):
                    span_line, span_col = file.text_position(pos)
                    line_highlights = highlights[span_line]
                    line_highlights.extend([" "] * (span_col - len(line_highlights)))
                    line_highlights[span_col - 1] = "^"

            line_spans = spans.close_gaps(line_mode=True)

            out.append(f"{file}:\n")

            max_line = max(file.text_position(span.file_end)[0] for span in line_spans.spans) + 1
            max_line = min(len(file.newlines) + 1, max_line)
            line_digits = max(len(str(max_line)), 2)

            for chunk_index, span in enumerate(line_spans.spans):
                start_line, _ = file.text_position(span.file_start)
                end_line, _ = file.text_position(span.file_end)

                context_start_line = max(1, start_line - 1)
                context_end_line = min(len(file.newlines) + 1, end_line + 1)

                if chunk_index > 0:
                    out.append(f"{' ':{line_digits}} :\n")

                for line_nr, line in enumerate(
                    file.text_lines(context_start_line, context_end_line).splitlines(),
                    context_start_line,
                ):
                    out.append(f"{line_nr:{line_digits}} | {line}\n")
                    if line_nr in highlights:
                        out.append(f"{' ':{line_digits}} | {''.join(highlights[line_nr])}\n")

        return "".join(out)
