import textwrap

from doc_quality.markdown import build_sections, norm_heading


def test_build_sections_h2_includes_nested_until_next_h2_or_h1():
    md = textwrap.dedent(
        """
        # Top

        ## A
        text A

        ### A1
        text A1

        #### A1a
        text A1a

        ## B
        text B
        """
    ).strip("\n")

    headings, sections = build_sections(md)
    assert headings, "Headings should be extracted"

    a = sections[norm_heading("A")][0]["text"]
    assert "text A" in a
    # Nested headings/content must be included in parent section
    assert "### A1" in a
    assert "text A1" in a
    assert "#### A1a" in a
    assert "text A1a" in a

    # Must stop before the next H2 ("B")
    assert "## B" not in a
    assert "text B" not in a


def test_build_sections_h3_includes_nested_until_next_h3_or_h2_or_h1():
    md = textwrap.dedent(
        """
        ## A
        pre

        ### A1
        text A1

        #### A1a
        text A1a

        ### A2
        text A2
        """
    ).strip("\n")

    _, sections = build_sections(md)

    a1 = sections[norm_heading("A1")][0]["text"]
    assert "text A1" in a1
    assert "#### A1a" in a1
    assert "text A1a" in a1

    # Must stop before next H3 ("A2")
    assert "### A2" not in a1
    assert "text A2" not in a1
