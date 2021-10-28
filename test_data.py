import logging
import sqlalchemy

from time import sleep

from slacrs import Slacrs

from slacrs.model import (
    Challenge,
    TargetImage,
    Target,
    Input,
    InputTag,
    Bitmap,
    Pov,
    PluginMessage,
    PluginDescription,
    InteractionURL,
    Trace,
)

from slacrs.model.schema import (
    ChallengeSchema,
    TargetImageSchema,
    TargetSchema,
    InputSchema,
    InputTagSchema,
    PovSchema,
    TraceSchema,
    PluginDescriptionSchema
)


logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
l = logging.getLogger(__name__)

seed_types = [
            "non-crashing",
            "crashing",
            "leaking",
            "non-terminating",
            "exploit",
        ]
# The database can be passed as a kwarg, or using the SLACRS_DATABASE env var.
s = Slacrs(database="postgresql+psycopg2://checrs:password@localhost:5432")

def push_to_db(obj):
    # Make a new session to keep seperatly from the object level "read" session
    session = s.session()
    try:
        if session.query(type(obj)).filter(type(obj).id == obj.id).count() == 0:
            session.add(obj)
            session.commit()

            session.refresh(obj)
            session.expunge(obj)
        else:
            l.error(f"{obj} already exists in db")
    except sqlalchemy.exc.IntegrityError as e:
        l.debug(f"Error pushing to db: {e}")
    except sqlalchemy.exc.InvalidRequestError as e:
        l.debug(f"Error pushing to db: {e}")
    except sqlalchemy.exc.OperationalError as e:
        l.debug("Error pushing to db: %s", str(e))
    finally:
        session.close()
# To read/write to the database, you need a session
try:
    challenge = Challenge(name="my_challenge")
    push_to_db(challenge)

    target = Target(name="hamlin", challenge_id=challenge.id)
    push_to_db(target)

    target_image = TargetImage(
        name="localhost:5010/ta3_hamlin", target_id=target.id
    )
    push_to_db(target_image)

    inp = Input(value=b"a" * 100, target_image_id=target_image.id)
    push_to_db(inp)
    inp_tag = InputTag(value="non-crashing", input_id=inp.id)
    push_to_db(inp_tag)

    inp2 = Input(value=b"b" * 100, target_image_id=target_image.id)
    push_to_db(inp2)
    for seed_type in seed_types:
        inp_tag_2 = InputTag(value=seed_type, input_id=inp2.id)
        push_to_db(inp_tag_2)

    # Add many large input cases
    for i in range(200):
        inp = Input(value=b"X" * 100000, target_image_id=target_image.id)
        push_to_db(inp)
        inp_tag = InputTag(value="non-crashing", input_id=inp.id)
        push_to_db(inp_tag)

    # Add some manually provided input cases
    for i in range(20):
        inp = Input(value=b"Manual..." * 5, target_image_id=target_image.id)
        push_to_db(inp)

    pov = Pov(pov='l.debug("HELLO WORLD!")', input_id=inp2.id)
    push_to_db(pov)

    interaction_url = InteractionURL(
        url="https://www.youtube.com/embed/oHg5SJYRHA0",
        target_image_id=target_image.id,
        interaction_type="interaction_server",
    )
    push_to_db(interaction_url)

    interaction_endpoint = InteractionURL(
        url="tcp://127.0.0.1:8888",
        target_image_id=target_image.id,
        interaction_type="socket_interaction_server",
    )
    push_to_db(interaction_endpoint)
except sqlalchemy.exc.InvalidRequestError as e:
    print("INVALID REQUEST")
try:
    plugin_desc = PluginDescription(name="test_plugin")
    push_to_db(plugin_desc)
except sqlalchemy.exc.InvalidRequestError as e:
    pass

sleep(2)
# Add some manually provided input cases
for i in range(20):
    print("Adding a new manual seed")
    inp = Input(value=b"new manual seed %d" % i, target_image_id=target_image.id)
    push_to_db(inp)
    sleep(2)