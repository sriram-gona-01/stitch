from lightwork.cli import main


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "usage: lw" in capsys.readouterr().out
