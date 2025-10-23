
def analyze_intent(text: str) -> str:
    # Very naive decomposition; replace with LLM-assisted analyzer if needed.
    lines = []
    lines.append("目的: ユーザーの入力を達成する")
    lines.append("制約: 安全/簡潔/正確")
    lines.append("視点: ユースケースに即した実装志向")
    lines.append("期待: 具体・短文・即使える成果物")
    return "\n".join(lines)
