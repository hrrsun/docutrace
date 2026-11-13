from pptx import Presentation
from pptx.util import Inches
from ingest import parse


def test_course_slides_keep_slide_and_table_location(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(6), Inches(1))
    box.text = "梯度表示局部上升最快方向"
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(5), Inches(2)).table
    for row, values in zip(table.rows, [["参数", "数值"], ["学习率", "0.1"]]):
        for cell, value in zip(row.cells, values):
            cell.text = value
    path = tmp_path / "course.pptx"
    deck.save(path)
    units, notes = parse(path)
    assert len(units) == 2
    assert "幻灯片 1" in units[0].loc
    assert "学习率 | 0.1" in units[1].text and "行 2" in units[1].loc
