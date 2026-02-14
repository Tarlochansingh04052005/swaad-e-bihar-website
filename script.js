const navCta = document.querySelector(".nav__cta");
const heroPrimary = document.querySelector(".primary");
const ghostButtons = document.querySelectorAll(".ghost");

const scrollToOrder = () => {
  const section = document.querySelector("#order");
  if (section) {
    section.scrollIntoView({ behavior: "smooth" });
  }
};

if (navCta) {
  navCta.addEventListener("click", scrollToOrder);
}

if (heroPrimary) {
  heroPrimary.addEventListener("click", scrollToOrder);
}

ghostButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const section = document.querySelector("#menu");
    if (section) {
      section.scrollIntoView({ behavior: "smooth" });
    }
  });
});

