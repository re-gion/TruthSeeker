from app.services.consultation_workflow import build_moderator_summary


def test_moderator_fallback_synthesizes_conclusions_instead_of_copying_chat():
    expert_message = (
        "（1）对于第三点——“未执行WHOIS查询moroba.com.br、未检索关联子域名、"
        "未检索'云邮通'与'Halifax'共现记录。经验库RAG提示OSINT补充路径未落实，"
        "需明确是否追加OSINT调查或接受TTP理解受限。”——这个后面的情报溯源agent会进行，"
        "电子取证agent不需要进行，交给后面的情报溯源agent即可"
        "（2）对于第四点——“VirusTotal文件哈希检测状态degraded=true/scan_available=false/error”"
        "——该降级我觉得影响不大，这个检材只是用户随手上传的一张照片，互联网上很大概率没有相应的哈希，"
        "所以不做哈希检测也影响不大，因为就算做了也很可能是检测不出来啥"
        "（3）对于第五点，检材的时间和检测的时间关系不大，也许只是用户上传了一个之前的检材，"
        "时间差别对目前的检测任务基本无影响"
    )

    result = build_moderator_summary(messages=[
        {"role": "expert", "message_type": "expert_opinion", "message": expert_message},
        {"role": "user", "message_type": "user_message", "message": "好的，谢谢专家，专家说的我很认可"},
    ])

    summary = result["generated_summary"]
    assert "情报溯源 Agent" in summary
    assert "VirusTotal" in summary and "影响有限" in summary
    assert "时间差" in summary and "不影响" in summary
    assert "用户认可专家意见" in summary
    assert "本轮人机协同共收到" not in summary
    assert "未执行WHOIS查询moroba.com.br" not in summary
    assert len(summary) < len(expert_message)
