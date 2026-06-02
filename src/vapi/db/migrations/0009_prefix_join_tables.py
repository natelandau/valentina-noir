from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0008_auto_20260601_1527")]

    initial = False

    operations = [
        ops.AlterField(
            model_name="ChargenSession",
            name="characters",
            field=fields.ManyToManyField(
                "models.Character",
                unique=True,
                db_constraint=True,
                through="j_chargen_session_characters",
                forward_key="character_id",
                backward_key="chargen_session_id",
                related_name="chargen_sessions",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="DiceRoll",
            name="traits",
            field=fields.ManyToManyField(
                "models.Trait",
                unique=True,
                db_constraint=True,
                through="j_dice_roll_traits",
                forward_key="trait_id",
                backward_key="dice_roll_id",
                related_name="dice_rolls",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="QuickRoll",
            name="traits",
            field=fields.ManyToManyField(
                "models.Trait",
                unique=True,
                db_constraint=True,
                through="j_quick_roll_traits",
                forward_key="trait_id",
                backward_key="quick_roll_id",
                related_name="quick_rolls",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="VampireClan",
            name="disciplines",
            field=fields.ManyToManyField(
                "models.Trait",
                unique=True,
                db_constraint=True,
                through="j_vampire_clan_disciplines",
                forward_key="trait_id",
                backward_key="vampire_clan_id",
                related_name="clans",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="WerewolfAuspice",
            name="gifts",
            field=fields.ManyToManyField(
                "models.Trait",
                unique=True,
                db_constraint=True,
                through="j_werewolf_auspice_gifts",
                forward_key="trait_id",
                backward_key="werewolf_auspice_id",
                related_name="auspices",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="WerewolfTribe",
            name="gifts",
            field=fields.ManyToManyField(
                "models.Trait",
                unique=True,
                db_constraint=True,
                through="j_werewolf_tribe_gifts",
                forward_key="trait_id",
                backward_key="werewolf_tribe_id",
                related_name="tribes",
                on_delete=OnDelete.CASCADE,
            ),
        ),
    ]
