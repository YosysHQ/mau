from __future__ import annotations

from textwrap import dedent


def test_example():
    # example begin
    import yosys_mau.config_parser as cfg
    from yosys_mau import source_str
    from yosys_mau.source_str import report

    class Options(cfg.ConfigOptions):
        mode = cfg.Option(cfg.EnumValue("bmc", "prove"))
        depth = cfg.Option(cfg.IntValue(min=0), default=20)
        multiclock = cfg.Option(cfg.BoolValue(), default=False)

    class Engines(cfg.ConfigCommands):
        def setup(self):
            self.smtbmc_args: list[str] = []
            self.abc_args: list[str] = []

        @cfg.command(cfg.StrValue())
        def smtbmc(self, arguments: str):
            self.smtbmc_args.append(arguments)

        @cfg.command(cfg.StrValue())
        def abc(self, arguments: str):
            self.abc_args.append(arguments)

        def unrecognized_command(self, command: cfg.ConfigCommand):
            raise report.InputError(
                command.name,
                f"unrecognized engine `{command.name}`",
            )

    class ExampleConfig(cfg.ConfigParser):
        file = cfg.StrSection().with_arguments()

        @cfg.postprocess_section(cfg.StrSection())
        def files(self, section: str) -> list[str]:
            return section.splitlines()

        script = cfg.StrSection()
        options = cfg.OptionsSection(Options)
        engines = cfg.CommandsSection(Engines, required=True)
        # example end

    example_input = """\
        [options]
        mode bmc
        depth 200
        multiclock on

        [engines]
        smtbmc yices
        smtbmc bitwuzla
        abc bmc3

        [script]
        read -formal top.sv

        [file top.sv]
        module top(...);
        ...
        endmodule

        [file defines.sv]
        `define SOME_DEFINE

        [files]
        more.sv
        source.sv
        files.sv
    """

    example_input = source_str.from_content(dedent(example_input), "test_input.sby")

    # assertions begin
    config = ExampleConfig(example_input)

    assert config.options.mode == "bmc"
    assert config.options.depth == 200
    assert config.options.multiclock

    assert config.engines.smtbmc_args == ["yices", "bitwuzla"]
    assert config.engines.abc_args == ["bmc3"]

    assert config.script == "read -formal top.sv\n\n"

    assert config.file["top.sv"] == "module top(...);\n...\nendmodule\n\n"
    assert config.file["defines.sv"] == "`define SOME_DEFINE\n\n"

    assert config.files == ["more.sv", "source.sv", "files.sv"]
    # assertions end
