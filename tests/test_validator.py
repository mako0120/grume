from grume.models import PageCopy, PostPackage
from grume.validator import PostValidator


def test_duplicate_strong_expression_is_rejected(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        """
style:
  max_caption_chars: 90
strong_expressions:
  - 優勝すぎる
""",
        encoding="utf-8",
    )
    validator = PostValidator(str(rules))
    post = PostPackage(
        design_title="x",
        store_name="店",
        area="大阪",
        cover_subcopy="sub",
        cover_hook="hook",
        pages=[
            PageCopy(page_index=1, filename="a.jpg", text="優勝すぎる"),
            PageCopy(page_index=2, filename="b.jpg", text="これも優勝すぎる"),
        ],
    )
    errors = validator.validate(post, {"a.jpg", "b.jpg"})
    assert any("強い表現が重複" in error for error in errors)
